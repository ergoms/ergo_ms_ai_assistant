import json
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from ..permissions import CanViewAiAssistant
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone

from src.core.utils.mixins import SwaggerSafeMixin

from ..ollama_gateway import chat as ollama_chat, resolved_model
from ..models import ChatSession, ChatMessage
from ..skills.integration import execute_skill_from_llm_response
from ..file_uploads import (
    collect_chat_upload_infos,
    create_temp_knowledge_document,
    extract_text_from_upload_info,
)
from ..rag import (
    RAGIndexingService,
    DocumentParseError,
)
from ..settings import (
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
)
from .helpers import _get_rag_context, _safe_json_dumps, _get_rag_services

logger = logging.getLogger(__name__)

class ChatView(SwaggerSafeMixin, APIView):
    """
    POST /api/ai_assistant/chat/
    Простой RAG чат для общих вопросов (без streaming)
    
    Body (JSON):
    {
        "message": "...",
        "session_id": "uuid",
        "module": "chat",
        "files_paths": [{"path": "...", "original_name": "..."}],  # media_api
        "file_path": "..."  # одиночный путь (опционально)
    }
    multipart fallback: files / file
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        if self.is_swagger_fake_view():
            return Response({'success': True})

        message = request.data.get('message')
        ollama_config = request.data.get('ollama_config')  # Настройки Ollama из module-config
        session_id = request.data.get('session_id')
        module = request.data.get('module', 'chat')
        upload_infos = collect_chat_upload_infos(request)
        
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

            model_name = resolved_model(ollama_config)
            temperature = (ollama_config or {}).get('temperature', 0)
            
            # Формируем массив сообщений для chat API с сохранением контекста
            messages = []
            
            system_prompt_parts = []
            if upload_infos:
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
            
            previous_messages = session.messages.order_by('created_at')[:10]
            for msg in previous_messages:
                if msg.message_type == ChatMessage.MESSAGE_TYPE_USER:
                    messages.append({"role": "user", "content": msg.content})
                elif msg.message_type == ChatMessage.MESSAGE_TYPE_ASSISTANT:
                    messages.append({"role": "assistant", "content": msg.content})
            
            uploaded_file_context = ""
            vectorized_document_ids = []
            
            if session.metadata and 'vectorized_documents' in session.metadata:
                vectorized_document_ids = session.metadata['vectorized_documents']
            
            if upload_infos:
                if enable_vectorization:
                    try:
                        embeddings_service, _ = _get_rag_services(ollama_config)
                        indexing_service = RAGIndexingService(
                            embeddings_service=embeddings_service,
                            chunk_size=RAG_CHUNK_SIZE,
                            chunk_overlap=RAG_CHUNK_OVERLAP,
                        )
                        
                        new_document_ids = []
                        for info in upload_infos:
                            name = info.get('name') or 'file'
                            try:
                                temp_doc = create_temp_knowledge_document(
                                    user=request.user,
                                    session=session,
                                    info=info,
                                )
                                indexing_result = indexing_service.index_document(temp_doc, force_reindex=True)
                                
                                if indexing_result.get('success'):
                                    new_document_ids.append(str(temp_doc.id))
                                    logger.info(f"Файл {name} успешно проиндексирован (ID: {temp_doc.id})")
                                else:
                                    logger.warning(f"Не удалось проиндексировать файл {name}: {indexing_result.get('error')}")
                                    temp_doc.delete()
                                    
                            except Exception as e:
                                logger.error(f"Ошибка векторизации файла {name}: {e}", exc_info=True)
                        
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
                
                if not enable_vectorization:
                    file_contexts = []
                    for info in upload_infos:
                        name = info.get('name') or 'file'
                        try:
                            extracted_content, _detected_type = extract_text_from_upload_info(info)
                            if extracted_content:
                                max_file_context_length = 2000
                                if len(extracted_content) > max_file_context_length:
                                    extracted_content = extracted_content[:max_file_context_length] + "..."
                                file_contexts.append(f"[СОДЕРЖИМОЕ ФАЙЛА: {name}]\n{extracted_content}\n[/СОДЕРЖИМОЕ ФАЙЛА]")
                        except DocumentParseError as e:
                            logger.warning(f"Не удалось извлечь текст из файла {name}: {e}")
                        except Exception as e:
                            logger.error(f"Ошибка обработки файла {name}: {e}", exc_info=True)
                    
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
            answer = ollama_chat(
                messages,
                ollama_config=ollama_config,
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
                'model': model_name,
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

