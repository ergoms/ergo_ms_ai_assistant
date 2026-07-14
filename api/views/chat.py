import json
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.viewsets import ViewSet
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.http import StreamingHttpResponse
from django.utils import timezone

from src.core.utils.mixins import SwaggerSafeMixin
from ..ollama_gateway import create_llm_client
from ..models import ChatSession, ChatMessage, KnowledgeDocument
from ..skills.integration import execute_skill_from_llm_response
from ..rag import (
    RAGIndexingService,
    DocumentParserService,
    DocumentParseError,
)
from ..settings import (
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
)
from .helpers import _get_rag_context, _safe_json_dumps

logger = logging.getLogger(__name__)

class ChatView(APIView):
    """
    POST /api/ai_assistant/chat/
    Простой RAG чат для общих вопросов (без streaming)
    
    Body (JSON или multipart/form-data):
    {
        "message": "Как работает система?",
        "session_id": "uuid",  # опционально, для продолжения существующего чата
        "module": "chat",  # опционально, модуль AI ассистента
        "file": <file>  # опционально, файл для анализа (Word, PDF, TXT)
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        message = request.data.get('message')
        ollama_config = request.data.get('ollama_config')  # Настройки Ollama из module-config
        session_id = request.data.get('session_id')
        module = request.data.get('module', 'chat')
        uploaded_files = request.FILES.getlist('files')  # Загруженные файлы (множественная загрузка)
        # Для обратной совместимости поддерживаем и одиночный файл
        if not uploaded_files:
            single_file = request.FILES.get('file')
            if single_file:
                uploaded_files = [single_file]
        
        # Получаем флаг векторизации
        enable_vectorization = request.data.get('enable_vectorization', False)
        if isinstance(enable_vectorization, str):
            enable_vectorization = enable_vectorization.lower() in ('true', '1', 'yes')
        
        # Обрабатываем ollama_config если он пришел как строка JSON (из FormData)
        if isinstance(ollama_config, str):
            try:
                ollama_config = json.loads(ollama_config)
            except (json.JSONDecodeError, TypeError):
                ollama_config = None
        
        if not message or not message.strip():
            return Response({
                'success': False,
                'error': 'Не указано сообщение'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Получаем или создаем сессию чата
            if session_id:
                try:
                    session = ChatSession.objects.get(id=session_id, user=request.user)
                except ChatSession.DoesNotExist:
                    session = None
            else:
                session = None
            
            # Получаем document_id из запроса (для модуля docs)
            document_id = request.data.get('document_id')
            
            if not session:
                # Создаем новую сессию с metadata, если есть document_id
                session_metadata = {}
                if document_id:
                    session_metadata['document_id'] = document_id
                session = ChatSession.objects.create(
                    user=request.user,
                    module=module,
                    title=message[:50] if message else 'Новый чат',
                    metadata=session_metadata
                )
            else:
                # Обновляем metadata сессии, если передан document_id
                if document_id:
                    if not session.metadata:
                        session.metadata = {}
                    session.metadata['document_id'] = document_id
                    session.save(update_fields=['metadata'])
            
            # Сохраняем сообщение пользователя
            user_message = ChatMessage.objects.create(
                session=session,
                message_type=ChatMessage.MESSAGE_TYPE_USER,
                content=message,
                metadata={'ollama_config': ollama_config} if ollama_config else {}
            )
            
            # Засекаем время начала запроса
            request_started_at = timezone.now()

            runtime_config, client = create_llm_client(ollama_config)
            temperature = (ollama_config or {}).get('temperature', 0)
            
            # Формируем массив сообщений для chat API с сохранением контекста
            messages = []
            
            # Добавляем системный промпт с инструкциями по работе с файлами
            system_prompt_parts = []
            if uploaded_files:
                if enable_vectorization:
                    system_prompt_parts.append(
                        "Пользователь загрузил файлы, которые были проиндексированы с помощью векторного поиска. "
                        "Используй информацию из векторного поиска для точных и релевантных ответов. "
                        "Учитывай контекст из всех загруженных файлов при ответе на вопросы."
                    )
                else:
                    system_prompt_parts.append(
                        "Пользователь загрузил файлы. Используй информацию из загруженных файлов для ответа на вопросы. "
                        "Учитывай содержимое всех загруженных файлов при формировании ответа."
                    )
            
            if system_prompt_parts:
                messages.append({
                    "role": "system",
                    "content": "\n".join(system_prompt_parts)
                })
            
            # Добавляем историю чата из БД (последние 10 сообщений для контекста)
            previous_messages = session.messages.order_by('created_at')[:10]
            for msg in previous_messages:
                if msg.message_type == ChatMessage.MESSAGE_TYPE_USER:
                    messages.append({"role": "user", "content": msg.content})
                elif msg.message_type == ChatMessage.MESSAGE_TYPE_ASSISTANT:
                    messages.append({"role": "assistant", "content": msg.content})
            
            # Обрабатываем загруженные файлы, если они есть
            uploaded_file_context = ""
            vectorized_document_ids = []
            
            # Получаем уже проиндексированные документы из сессии (если есть)
            if session.metadata and 'vectorized_documents' in session.metadata:
                vectorized_document_ids = session.metadata['vectorized_documents']
            
            if uploaded_files:
                if enable_vectorization:
                    # Векторизация: создаем временные KnowledgeDocument и индексируем их
                    try:
                        embeddings_service, _ = _get_rag_services(ollama_config)
                        indexing_service = RAGIndexingService(
                            embeddings_service=embeddings_service,
                            chunk_size=RAG_CHUNK_SIZE,
                            chunk_overlap=RAG_CHUNK_OVERLAP,
                        )
                        
                        new_document_ids = []
                        for uploaded_file in uploaded_files:
                            try:
                                # Создаем временный KnowledgeDocument
                                temp_doc = KnowledgeDocument.objects.create(
                                    user=request.user,
                                    title=f"Временный документ: {uploaded_file.name}",
                                    file=uploaded_file,
                                    source=f"chat_upload_{session.id}",
                                    metadata={
                                        'session_id': str(session.id),
                                        'is_temporary': True,
                                        'uploaded_at': timezone.now().isoformat(),
                                    }
                                )
                                
                                # Индексируем документ
                                indexing_result = indexing_service.index_document(temp_doc, force_reindex=True)
                                
                                if indexing_result.get('success'):
                                    new_document_ids.append(str(temp_doc.id))
                                    logger.info(f"Файл {uploaded_file.name} успешно проиндексирован (ID: {temp_doc.id})")
                                else:
                                    logger.warning(f"Не удалось проиндексировать файл {uploaded_file.name}: {indexing_result.get('error')}")
                                    temp_doc.delete()  # Удаляем документ, если индексация не удалась
                                    
                            except Exception as e:
                                logger.error(f"Ошибка векторизации файла {uploaded_file.name}: {e}", exc_info=True)
                        
                        # Сохраняем ID новых документов в metadata сессии
                        if new_document_ids:
                            if not session.metadata:
                                session.metadata = {}
                            if 'vectorized_documents' not in session.metadata:
                                session.metadata['vectorized_documents'] = []
                            session.metadata['vectorized_documents'].extend(new_document_ids)
                            session.save(update_fields=['metadata'])
                            vectorized_document_ids.extend(new_document_ids)
                            
                    except Exception as e:
                        logger.error(f"Ошибка при векторизации файлов: {e}", exc_info=True)
                
                # Извлекаем текст из файлов для обычного контекста (если векторизация не включена)
                if not enable_vectorization:
                    file_contexts = []
                    for uploaded_file in uploaded_files:
                        try:
                            from io import BytesIO
                            file_obj = BytesIO(uploaded_file.read())
                            extracted_content, detected_type = DocumentParserService.parse_document(
                                file_obj=file_obj,
                                filename=uploaded_file.name
                            )
                            if extracted_content:
                                # Ограничиваем размер контекста из файла
                                max_file_context_length = 2000  # Примерно 2000 символов
                                if len(extracted_content) > max_file_context_length:
                                    extracted_content = extracted_content[:max_file_context_length] + "..."
                                file_contexts.append(f"[СОДЕРЖИМОЕ ФАЙЛА: {uploaded_file.name}]\n{extracted_content}\n[/СОДЕРЖИМОЕ ФАЙЛА]")
                        except DocumentParseError as e:
                            logger.warning(f"Не удалось извлечь текст из файла {uploaded_file.name}: {e}")
                        except Exception as e:
                            logger.error(f"Ошибка обработки файла {uploaded_file.name}: {e}", exc_info=True)
                    
                    if file_contexts:
                        uploaded_file_context = "\n\n".join(file_contexts) + "\n\nИспользуй информацию из загруженных файлов для ответа на вопрос пользователя."
            
            # Получаем контекст из базы знаний RAG
            rag_context = ""
            rag_chunks = []
            
            # Если векторизация включена, используем векторный поиск по загруженным файлам
            if enable_vectorization and vectorized_document_ids:
                rag_context, rag_chunks = _get_rag_context(
                    query=message,
                    user=request.user,
                    ollama_config=ollama_config,
                    document_ids=vectorized_document_ids,
                )
            elif module == 'docs':
                # Получаем document_id из metadata сессии или из запроса
                document_id = None
                if session.metadata and 'document_id' in session.metadata:
                    document_id = session.metadata['document_id']
                elif request.data.get('document_id'):
                    document_id = request.data.get('document_id')
                
                # Получаем контекст из базы знаний RAG только для модуля docs
                document_ids = [document_id] if document_id else None
                rag_context, rag_chunks = _get_rag_context(
                    query=message,
                    user=request.user,
                    ollama_config=ollama_config,
                    document_ids=document_ids,
                )
            
            # Формируем текущее сообщение пользователя с дополнительными контекстами
            user_message_parts = []
            
            if uploaded_file_context:
                user_message_parts.append(uploaded_file_context)
            
            if rag_context:
                user_message_parts.append(
                    f"[ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n{rag_context}\n[/ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n\n"
                    "Используй эту информацию для ответа на вопрос пользователя. "
                    "Если в базе знаний есть релевантная информация, обязательно используй её. "
                    "Если информации нет, отвечай на основе своих знаний."
                )
            
            user_message_parts.append(message)
            user_message = "\n\n".join(user_message_parts)
            
            # Добавляем текущее сообщение пользователя
            messages.append({"role": "user", "content": user_message})
            
            # Используем chat API для сохранения контекста
            answer = client.chat(
                messages,
                temperature=temperature,
                stream=False,
            ).strip()
            
            # Проверяем, нужно ли выполнить навык из ответа LLM
            skill_result, cleaned_answer, skill_display_name, skill_call = execute_skill_from_llm_response(
                answer,
                message,
                context={'user': request.user, 'session': session, 'module': module}
            )
            
            # Если навык был выполнен, добавляем результат в ответ
            if skill_result and skill_result.success:
                if cleaned_answer:
                    answer = f"{skill_result.result}\n\n{cleaned_answer}"
                else:
                    answer = skill_result.result
            elif skill_result and not skill_result.success:
                answer = f"{cleaned_answer}\n\n⚠️ Ошибка выполнения навыка: {skill_result.error}"
            else:
                answer = cleaned_answer if cleaned_answer else answer
            
            
            # Засекаем время получения ответа
            response_received_at = timezone.now()
            processing_time = int((response_received_at - request_started_at).total_seconds() * 1000)
            
            # Формируем metadata с данными навыка
            message_metadata = {
                'model': runtime_config.model,
                'skill_name': skill_display_name,
                'skill_call': skill_call,
            }
            if ollama_config:
                message_metadata['ollama_config'] = ollama_config
            
            # Добавляем данные навыка (например, конфигурацию графика)
            if skill_result and skill_result.success and skill_result.metadata:
                # Проверяем, это график?
                if 'chart_config' in skill_result.metadata:
                    message_metadata['chart_config'] = skill_result.metadata['chart_config']
            
            # Сохраняем ответ ассистента
            assistant_message = ChatMessage.objects.create(
                session=session,
                message_type=ChatMessage.MESSAGE_TYPE_ASSISTANT,
                content=answer,
                request_started_at=request_started_at,
                response_received_at=response_received_at,
                processing_time_ms=processing_time,
                metadata=message_metadata
            )
            
            # Обновляем время сессии
            session.updated_at = timezone.now()
            session.save(update_fields=['updated_at'])
            
            # Формируем ответ
            response_data = {
                'success': True,
                'response': answer,
                'message': answer,  # Для совместимости
                'session_id': str(session.id),
                'message_id': str(assistant_message.id),
                'processing_time_ms': processing_time,
                'timestamp': assistant_message.created_at.isoformat(),
                'skill_name': skill_display_name,
                'skill_call': skill_call,
            }
            # Добавляем конфигурацию графика, если есть
            if 'chart_config' in message_metadata:
                response_data['chart_config'] = message_metadata['chart_config']
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatStreamView(APIView):
    """
    POST /api/ai_assistant/chat/stream/
    RAG чат с поддержкой Server-Sent Events (SSE) для streaming ответов
    
    Body (JSON или multipart/form-data):
    {
        "message": "Как работает система?",
        "session_id": "uuid",  # опционально, для продолжения существующего чата
        "module": "chat",  # опционально, модуль AI ассистента
        "file": <file>  # опционально, файл для анализа (Word, PDF, TXT)
    }
    
    Response: SSE stream с событиями:
    - {"type": "chunk", "text": "..."} - часть ответа
    - {"type": "done", "full_response": "...", "session_id": "...", "message_id": "...", "processing_time_ms": 123} - завершение
    - {"type": "error", "message": "..."} - ошибка
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        message = request.data.get('message')
        ollama_config = request.data.get('ollama_config')
        session_id = request.data.get('session_id')
        module = request.data.get('module', 'chat')
        uploaded_files = request.FILES.getlist('files')  # Загруженные файлы (множественная загрузка)
        # Для обратной совместимости поддерживаем и одиночный файл
        if not uploaded_files:
            single_file = request.FILES.get('file')
            if single_file:
                uploaded_files = [single_file]
        
        # Получаем флаг векторизации
        enable_vectorization = request.data.get('enable_vectorization', False)
        if isinstance(enable_vectorization, str):
            enable_vectorization = enable_vectorization.lower() in ('true', '1', 'yes')
        
        # Обрабатываем ollama_config если он пришел как строка JSON (из FormData)
        if isinstance(ollama_config, str):
            try:
                ollama_config = json.loads(ollama_config)
            except (json.JSONDecodeError, TypeError):
                ollama_config = None
        
        if not message or not message.strip():
            return Response({
                'success': False,
                'error': 'Не указано сообщение'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Получаем или создаем сессию чата
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                session = None
        else:
            session = None
        
        # Получаем document_id из запроса (для модуля docs)
        document_id = request.data.get('document_id')
        
        if not session:
            # Создаем новую сессию с metadata, если есть document_id
            session_metadata = {}
            if document_id:
                session_metadata['document_id'] = document_id
            session = ChatSession.objects.create(
                user=request.user,
                module=module,
                title=message[:50] if message else 'Новый чат',
                metadata=session_metadata
            )
        else:
            # Обновляем metadata сессии, если передан document_id
            if document_id:
                if not session.metadata:
                    session.metadata = {}
                session.metadata['document_id'] = document_id
                session.save(update_fields=['metadata'])
        
        # Сохраняем сообщение пользователя
        user_message = ChatMessage.objects.create(
            session=session,
            message_type=ChatMessage.MESSAGE_TYPE_USER,
            content=message,
            metadata={'ollama_config': ollama_config} if ollama_config else {}
        )
        
        def event_stream():
            import threading
            
            try:
                # Засекаем время начала запроса
                request_started_at = timezone.now()
                
                runtime_config, client = create_llm_client(ollama_config)
                temperature = (ollama_config or {}).get('temperature', 0)
                
                # Формируем массив сообщений для chat API с сохранением контекста
                messages = []
                
                # Обрабатываем загруженные файлы, если они есть
                uploaded_file_context = ""
                vectorized_document_ids = []
                
                # Получаем уже проиндексированные документы из сессии (если есть)
                if session.metadata and 'vectorized_documents' in session.metadata:
                    vectorized_document_ids = session.metadata['vectorized_documents']
                
                if uploaded_files:
                    if enable_vectorization:
                        # Векторизация: создаем временные KnowledgeDocument и индексируем их
                        try:
                            embeddings_service, _ = _get_rag_services(ollama_config)
                            indexing_service = RAGIndexingService(
                                embeddings_service=embeddings_service,
                                chunk_size=RAG_CHUNK_SIZE,
                                chunk_overlap=RAG_CHUNK_OVERLAP,
                            )
                            
                            new_document_ids = []
                            for uploaded_file in uploaded_files:
                                try:
                                    # Создаем временный KnowledgeDocument
                                    temp_doc = KnowledgeDocument.objects.create(
                                        user=request.user,
                                        title=f"Временный документ: {uploaded_file.name}",
                                        file=uploaded_file,
                                        source=f"chat_upload_{session.id}",
                                        metadata={
                                            'session_id': str(session.id),
                                            'is_temporary': True,
                                            'uploaded_at': timezone.now().isoformat(),
                                        }
                                    )
                                    
                                    # Индексируем документ
                                    indexing_result = indexing_service.index_document(temp_doc, force_reindex=True)
                                    
                                    if indexing_result.get('success'):
                                        new_document_ids.append(str(temp_doc.id))
                                        logger.info(f"Файл {uploaded_file.name} успешно проиндексирован (ID: {temp_doc.id})")
                                    else:
                                        logger.warning(f"Не удалось проиндексировать файл {uploaded_file.name}: {indexing_result.get('error')}")
                                        temp_doc.delete()  # Удаляем документ, если индексация не удалась
                                        
                                except Exception as e:
                                    logger.error(f"Ошибка векторизации файла {uploaded_file.name}: {e}", exc_info=True)
                            
                            # Сохраняем ID новых документов в metadata сессии
                            if new_document_ids:
                                if not session.metadata:
                                    session.metadata = {}
                                if 'vectorized_documents' not in session.metadata:
                                    session.metadata['vectorized_documents'] = []
                                session.metadata['vectorized_documents'].extend(new_document_ids)
                                session.save(update_fields=['metadata'])
                                vectorized_document_ids.extend(new_document_ids)
                                
                        except Exception as e:
                            logger.error(f"Ошибка при векторизации файлов: {e}", exc_info=True)
                    
                    # Извлекаем текст из файлов для обычного контекста (если векторизация не включена)
                    if not enable_vectorization:
                        file_contexts = []
                        for uploaded_file in uploaded_files:
                            try:
                                from io import BytesIO
                                file_obj = BytesIO(uploaded_file.read())
                                extracted_content, detected_type = DocumentParserService.parse_document(
                                    file_obj=file_obj,
                                    filename=uploaded_file.name
                                )
                                if extracted_content:
                                    # Ограничиваем размер контекста из файла
                                    max_file_context_length = 2000  # Примерно 2000 символов
                                    if len(extracted_content) > max_file_context_length:
                                        extracted_content = extracted_content[:max_file_context_length] + "..."
                                    file_contexts.append(f"[СОДЕРЖИМОЕ ФАЙЛА: {uploaded_file.name}]\n{extracted_content}\n[/СОДЕРЖИМОЕ ФАЙЛА]")
                            except DocumentParseError as e:
                                logger.warning(f"Не удалось извлечь текст из файла {uploaded_file.name}: {e}")
                            except Exception as e:
                                logger.error(f"Ошибка обработки файла {uploaded_file.name}: {e}", exc_info=True)
                        
                        if file_contexts:
                            uploaded_file_context = "\n\n".join(file_contexts) + "\n\nИспользуй информацию из загруженных файлов для ответа на вопрос пользователя."
                
                # Получаем контекст из базы знаний RAG
                rag_context = ""
                rag_chunks = []
                
                # Если векторизация включена, используем векторный поиск по загруженным файлам
                if enable_vectorization and vectorized_document_ids:
                    rag_context, rag_chunks = _get_rag_context(
                        query=message,
                        user=request.user,
                        ollama_config=ollama_config,
                        document_ids=vectorized_document_ids,
                    )
                elif module == 'docs':
                    # Получаем document_id из metadata сессии или из запроса
                    document_id = None
                    if session.metadata and 'document_id' in session.metadata:
                        document_id = session.metadata['document_id']
                    elif request.data.get('document_id'):
                        document_id = request.data.get('document_id')
                    
                    # Получаем контекст из базы знаний RAG только для модуля docs
                    document_ids = [document_id] if document_id else None
                    rag_context, rag_chunks = _get_rag_context(
                        query=message,
                        user=request.user,
                        ollama_config=ollama_config,
                        document_ids=document_ids,
                    )
                
                # Добавляем системный промпт с инструкциями по работе с файлами
                system_prompt_parts = []
                if uploaded_files:
                    if enable_vectorization:
                        system_prompt_parts.append(
                            "Пользователь загрузил файлы, которые были проиндексированы с помощью векторного поиска. "
                            "Используй информацию из векторного поиска для точных и релевантных ответов. "
                            "Учитывай контекст из всех загруженных файлов при ответе на вопросы."
                        )
                    else:
                        system_prompt_parts.append(
                            "Пользователь загрузил файлы. Используй информацию из загруженных файлов для ответа на вопросы. "
                            "Учитывай содержимое всех загруженных файлов при формировании ответа."
                        )
                
                if system_prompt_parts:
                    messages.append({
                        "role": "system",
                        "content": "\n".join(system_prompt_parts)
                    })
                
                # Добавляем историю чата из БД (последние 10 сообщений для контекста)
                previous_messages = session.messages.order_by('created_at')[:10]
                for msg in previous_messages:
                    if msg.message_type == ChatMessage.MESSAGE_TYPE_USER:
                        messages.append({"role": "user", "content": msg.content})
                    elif msg.message_type == ChatMessage.MESSAGE_TYPE_ASSISTANT:
                        messages.append({"role": "assistant", "content": msg.content})
                
                # Формируем текущее сообщение пользователя с дополнительными контекстами
                user_message_parts = []
                
                if uploaded_file_context:
                    user_message_parts.append(uploaded_file_context)
                
                if rag_context:
                    user_message_parts.append(
                        f"[ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n{rag_context}\n[/ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n\n"
                        "Используй эту информацию для ответа на вопрос пользователя. "
                        "Если в базе знаний есть релевантная информация, обязательно используй её. "
                        "Если информации нет, отвечай на основе своих знаний."
                    )
                
                user_message_parts.append(message)
                user_message = "\n\n".join(user_message_parts)
                
                # Добавляем текущее сообщение пользователя
                messages.append({"role": "user", "content": user_message})
                
                # Оптимизация: используем Queue вместо списка
                from queue import Queue, Empty
                streaming_chunks_queue = Queue()
                result_container = {}
                exception_container = {}
                
                def stream_callback(text):
                    streaming_chunks_queue.put(text)
                
                def run_chat():
                    try:
                        result = client.chat(
                            messages,
                            temperature=temperature,
                            stream=True,
                            stream_callback=stream_callback,
                        )
                        result_container['response'] = result.strip()
                    except Exception as e:
                        exception_container['error'] = e
                    finally:
                        # Сигнал завершения
                        streaming_chunks_queue.put(None)
                
                # Запускаем в отдельном потоке
                chat_thread = threading.Thread(target=run_chat)
                chat_thread.start()
                
                # Оптимизация: используем блокирующее ожидание вместо активного polling
                while chat_thread.is_alive() or not streaming_chunks_queue.empty():
                    try:
                        chunk = streaming_chunks_queue.get(timeout=0.1)
                        if chunk is None:  # Сигнал завершения
                            break
                        yield f"data: {_safe_json_dumps({'type': 'chunk', 'text': chunk}, ensure_ascii=False)}\n\n"
                    except Empty:
                        continue
                
                chat_thread.join(timeout=5.0)
                
                # Проверяем ошибки
                if 'error' in exception_container:
                    raise exception_container['error']
                
                # Засекаем время получения ответа
                response_received_at = timezone.now()
                
                # Получаем полный ответ
                raw_response = result_container.get('response', '')
                
                # Проверяем, нужно ли выполнить навык из ответа LLM
                skill_result, cleaned_response, skill_display_name, skill_call = execute_skill_from_llm_response(
                    raw_response,
                    message,
                    context={'user': request.user, 'session': session, 'module': module}
                )
                
                # Формируем финальный ответ
                if skill_result and skill_result.success:
                    if cleaned_response:
                        full_response = f"{skill_result.result}\n\n{cleaned_response}"
                    else:
                        full_response = str(skill_result.result)
                elif skill_result and not skill_result.success:
                    full_response = f"{cleaned_response if cleaned_response else raw_response}\n\n⚠️ Ошибка выполнения навыка: {skill_result.error}"
                else:
                    full_response = cleaned_response if cleaned_response else raw_response
                
                processing_time = int((response_received_at - request_started_at).total_seconds() * 1000)
                
                # Формируем metadata с данными навыка
                message_metadata = {
                    'model': runtime_config.model,
                    'skill_name': skill_display_name,
                    'skill_call': skill_call,
                }
                if ollama_config:
                    message_metadata['ollama_config'] = ollama_config
                
                # Добавляем данные навыка (например, конфигурацию графика)
                if skill_result and skill_result.success and skill_result.metadata:
                    # Проверяем, это график?
                    if 'chart_config' in skill_result.metadata:
                        message_metadata['chart_config'] = skill_result.metadata['chart_config']
                
                # Сохраняем ответ ассистента
                assistant_message = ChatMessage.objects.create(
                    session=session,
                    message_type=ChatMessage.MESSAGE_TYPE_ASSISTANT,
                    content=full_response,
                    request_started_at=request_started_at,
                    response_received_at=response_received_at,
                    processing_time_ms=processing_time,
                    metadata=message_metadata
                )
                
                # Обновляем время сессии
                session.updated_at = timezone.now()
                session.save(update_fields=['updated_at'])
                
                # Формируем финальное событие
                done_event = {
                    'type': 'done',
                    'full_response': full_response,
                    'session_id': str(session.id),
                    'message_id': str(assistant_message.id),
                    'processing_time_ms': processing_time,
                    'timestamp': assistant_message.created_at.isoformat(),
                    'skill_name': skill_display_name,
                    'skill_call': skill_call,
                }
                # Добавляем конфигурацию графика, если есть
                if 'chart_config' in message_metadata:
                    done_event['chart_config'] = message_metadata['chart_config']
                
                yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        
        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ChatSessionViewSet(ViewSet, SwaggerSafeMixin):
    """
    ViewSet для работы с сессиями чатов
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        """
        GET /api/ai_assistant/chat_sessions/
        Получить список сессий чатов пользователя
        """
        user = self.get_safe_user()
        queryset = ChatSession.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        # Фильтрация по модулю
        module = request.query_params.get('module')
        if module:
            queryset = queryset.filter(module=module)
        
        sessions = []
        for session in queryset[:50]:  # Ограничиваем 50 последними
            sessions.append({
                'id': str(session.id),
                'title': session.title or 'Без названия',
                'module': session.module,
                'message_count': session.message_count,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'metadata': session.metadata or {},
            })
        
        return Response({
            'success': True,
            'sessions': sessions,
            'count': len(sessions),
        })
    
    def retrieve(self, request, pk=None):
        """
        GET /api/ai_assistant/chat_sessions/{id}/
        Получить сессию чата с сообщениями
        """
        user = self.get_safe_user()
        queryset = ChatSession.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        try:
            session = queryset.get(id=pk)
        except ChatSession.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Сессия не найдена'
            }, status=status.HTTP_404_NOT_FOUND)
        
        messages = []
        for msg in session.messages.all():
            messages.append({
                'id': str(msg.id),
                'type': msg.message_type,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
                'request_started_at': msg.request_started_at.isoformat() if msg.request_started_at else None,
                'response_received_at': msg.response_received_at.isoformat() if msg.response_received_at else None,
                'processing_time_ms': msg.processing_time_ms,
                'metadata': msg.metadata,
            })
        
        return Response({
            'success': True,
            'session': {
                'id': str(session.id),
                'title': session.title or 'Без названия',
                'module': session.module,
                'message_count': session.message_count,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'metadata': session.metadata or {},
            },
            'messages': messages,
        })
    
    def create(self, request):
        """
        POST /api/ai_assistant/chat_sessions/
        Создать новую сессию чата
        """
        user = self.get_safe_user()
        if not user:
            return Response({
                'success': False,
                'error': 'Пользователь не найден'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        title = request.data.get('title', 'Новый чат')
        module = request.data.get('module', 'chat')
        
        session = ChatSession.objects.create(
            user=user,
            title=title,
            module=module
        )
        return Response({
            'success': True,
            'session': {
                'id': str(session.id),
                'title': session.title,
                'module': session.module,
                'message_count': session.message_count,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
            }
        }, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, pk=None):
        """
        DELETE /api/ai_assistant/chat_sessions/{id}/
        Удалить сессию чата
        """
        user = self.get_safe_user()
        queryset = ChatSession.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        try:
            session = queryset.get(id=pk)
            session.delete()
            return Response({
                'success': True,
                'message': 'Сессия удалена'
            }, status=status.HTTP_200_OK)
        except ChatSession.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Сессия не найдена'
            }, status=status.HTTP_404_NOT_FOUND)

