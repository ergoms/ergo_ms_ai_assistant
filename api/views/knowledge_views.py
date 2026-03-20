import json
import logging

from django.http import FileResponse
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from ..assistant_settings import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE
from src.core.utils.mixins import SwaggerSafeMixin

from ..models import KnowledgeDocument
from ..rag import DocumentParseError, DocumentParserService, RAGIndexingError, RAGIndexingService
from ..rag_service import get_rag_services

logger = logging.getLogger(__name__)

class KnowledgeDocumentViewSet(ViewSet, SwaggerSafeMixin):
    """
    ViewSet для управления документами базы знаний RAG
    
    Поддерживает:
    - Загрузку файлов (Word, PDF, TXT) через multipart/form-data
    - Создание документов из текста через JSON
    - Автоматическое извлечение текста из файлов при индексации
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def list(self, request):
        """
        GET /api/ai_assistant/knowledge_documents/
        Получить список документов пользователя
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        documents = []
        for doc in queryset.order_by('-created_at'):
            # Определяем размер файла
            file_size = None
            file_url = None
            if doc.file:
                try:
                    file_size = doc.file.size
                    file_url = doc.file.url if hasattr(doc.file, 'url') else None
                except Exception:
                    pass
            
            documents.append({
                'id': str(doc.id),
                'title': doc.title,
                'source': doc.source,
                'has_file': bool(doc.file),
                'file_type': doc.file_type,
                'file_name': doc.file.name.split('/')[-1] if doc.file else None,
                'file_size': file_size,
                'file_url': file_url,
                'content_preview': (doc.content[:200] + '...' if doc.content and len(doc.content) > 200 else doc.content) if doc.content else None,
                'is_indexed': doc.is_indexed,
                'chunks_count': doc.chunks_count,
                'indexed_at': doc.indexed_at.isoformat() if doc.indexed_at else None,
                'created_at': doc.created_at.isoformat(),
                'updated_at': doc.updated_at.isoformat(),
                'metadata': doc.metadata,
            })
        
        return Response({
            'success': True,
            'documents': documents,
            'count': len(documents),
        }, status=status.HTTP_200_OK)
    
    def create(self, request):
        """
        POST /api/ai_assistant/knowledge_documents/
        Создать новый документ
        
        Поддерживает два режима:
        1. Загрузка файла (multipart/form-data):
           - file: файл (Word, PDF, TXT)
           - title: название документа
           - source: источник (опционально)
           - metadata: JSON метаданные (опционально)
           - index_immediately: индексировать сразу (опционально, default: false)
        
        2. Создание из текста (JSON):
           - title: название документа
           - content: текстовое содержимое
           - source: источник (опционально)
           - metadata: метаданные (опционально)
           - index_immediately: индексировать сразу (опционально)
        
        Если указан и файл, и content, приоритет у файла.
        """
        user = self.get_safe_user()
        
        title = request.data.get('title')
        uploaded_file = request.FILES.get('file')
        content = request.data.get('content')
        source = request.data.get('source', '')
        metadata = request.data.get('metadata', {})
        index_immediately = request.data.get('index_immediately', False)
        
        # Обработка metadata если это строка JSON
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        
        if not title:
            return Response({
                'success': False,
                'error': 'Не указано обязательное поле: title'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not uploaded_file and not content:
            return Response({
                'success': False,
                'error': 'Не указаны ни файл, ни текстовое содержимое. Укажите одно из: file или content'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            file_type = None
            extracted_content = None
            
            # Если загружен файл - определяем его тип
            if uploaded_file:
                file_type = DocumentParserService.get_file_type(uploaded_file.name)
                # Для файлов контент не обязателен, он извлечется при индексации
                # Но можно попробовать извлечь сразу, если index_immediately
                if index_immediately:
                    try:
                        from io import BytesIO
                        file_obj = BytesIO(uploaded_file.read())
                        extracted_content, detected_type = DocumentParserService.parse_document(
                            file_obj=file_obj,
                            filename=uploaded_file.name
                        )
                        file_type = detected_type
                        file_obj.seek(0)  # Возвращаемся в начало для сохранения файла
                        uploaded_file.seek(0)  # Возвращаемся в начало
                    except DocumentParseError as e:
                        # Если не удалось извлечь, продолжаем - извлечем при индексации
                        logger.warning(f"Не удалось извлечь текст из файла сразу: {e}")
            
            # Используем извлеченный контент или переданный
            final_content = extracted_content or content
            
            # Создаем документ
            document = KnowledgeDocument.objects.create(
                user=user,
                title=title,
                content=final_content,
                source=source or (uploaded_file.name if uploaded_file else ''),
                metadata=metadata,
                file_type=file_type,
            )
            
            # Сохраняем файл, если он был загружен
            if uploaded_file:
                document.file = uploaded_file
                document.save(update_fields=['file'])
            
            # Индексируем документ, если запрошено
            indexing_result = None
            if index_immediately:
                try:
                    embeddings_service, _ = get_rag_services()
                    indexing_service = RAGIndexingService(
                        embeddings_service=embeddings_service,
                        chunk_size=RAG_CHUNK_SIZE,
                        chunk_overlap=RAG_CHUNK_OVERLAP,
                    )
                    indexing_result = indexing_service.index_document(document)
                    # Обновляем объект документа из БД, чтобы получить актуальный chunks_count
                    document.refresh_from_db()
                except Exception as e:
                    logger.error("Ошибка индексации документа %s: %s", document.id, e, exc_info=True)
                    # Не прерываем создание документа, просто логируем ошибку
            
            return Response({
                'success': True,
                'document': {
                    'id': str(document.id),
                    'title': document.title,
                    'source': document.source,
                    'has_file': bool(document.file),
                    'file_type': document.file_type,
                    'file_name': document.file.name.split('/')[-1] if document.file else None,
                    'is_indexed': document.is_indexed,
                    'chunks_count': document.chunks_count,
                    'indexed_at': document.indexed_at.isoformat() if document.indexed_at else None,
                    'created_at': document.created_at.isoformat(),
                    'metadata': document.metadata,
                },
                'indexing_result': indexing_result,
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Ошибка создания документа: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def retrieve(self, request, pk=None):
        """
        GET /api/ai_assistant/knowledge_documents/{id}/
        Получить документ с chunks
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        try:
            document = queryset.get(id=pk)
            
            chunks = []
            for chunk in document.chunks.all().order_by('chunk_index'):
                chunks.append({
                    'id': str(chunk.id),
                    'chunk_index': chunk.chunk_index,
                    'content': chunk.content,
                    'start_char': chunk.start_char,
                    'end_char': chunk.end_char,
                    'embedding_model': chunk.embedding_model,
                    'has_embedding': bool(chunk.embedding),
                    'metadata': chunk.metadata,
                })
            
            # Информация о файле
            file_info = None
            if document.file:
                try:
                    file_info = {
                        'name': document.file.name.split('/')[-1],
                        'size': document.file.size,
                        'url': document.file.url if hasattr(document.file, 'url') else None,
                        'type': document.file_type,
                    }
                except Exception:
                    pass
            
            return Response({
                'success': True,
                'document': {
                    'id': str(document.id),
                    'title': document.title,
                    'content': document.content,
                    'source': document.source,
                    'file': file_info,
                    'file_type': document.file_type,
                    'is_indexed': document.is_indexed,
                    'chunks_count': document.chunks_count,
                    'indexed_at': document.indexed_at.isoformat() if document.indexed_at else None,
                    'created_at': document.created_at.isoformat(),
                    'updated_at': document.updated_at.isoformat(),
                    'metadata': document.metadata,
                    'chunks': chunks,
                },
            }, status=status.HTTP_200_OK)
            
        except KnowledgeDocument.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Документ не найден'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def update(self, request, pk=None):
        """
        PUT /api/ai_assistant/knowledge_documents/{id}/
        Обновить документ
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        try:
            document = queryset.get(id=pk)
            
            # Обновляем поля
            if 'title' in request.data:
                document.title = request.data['title']
            if 'content' in request.data:
                document.content = request.data['content']
                # Если изменили содержимое, сбрасываем статус индексации
                if document.is_indexed:
                    document.is_indexed = False
                    document.indexed_at = None
            if 'source' in request.data:
                document.source = request.data['source']
            if 'metadata' in request.data:
                document.metadata = request.data['metadata']
            
            document.save()
            
            return Response({
                'success': True,
                'document': {
                    'id': str(document.id),
                    'title': document.title,
                    'is_indexed': document.is_indexed,
                    'chunks_count': document.chunks_count,
                },
            }, status=status.HTTP_200_OK)
            
        except KnowledgeDocument.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Документ не найден'
            }, status=status.HTTP_404_NOT_FOUND)
    
    def destroy(self, request, pk=None):
        """
        DELETE /api/ai_assistant/knowledge_documents/{id}/
        Удалить документ (вместе с chunks)
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        try:
            document = queryset.get(id=pk)
            document.delete()  # Каскадное удаление chunks
            return Response({
                'success': True,
                'message': 'Документ удален'
            }, status=status.HTTP_200_OK)
            
        except KnowledgeDocument.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Документ не найден'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'], url_path='index')
    def index(self, request, pk=None):
        """
        POST /api/ai_assistant/knowledge_documents/{id}/index/
        Индексировать или переиндексировать документ
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        force_reindex = request.data.get('force', False)
        
        try:
            document = queryset.get(id=pk)
            
            embeddings_service, _ = get_rag_services()
            indexing_service = RAGIndexingService(
                embeddings_service=embeddings_service,
                chunk_size=RAG_CHUNK_SIZE,
                chunk_overlap=RAG_CHUNK_OVERLAP,
            )
            
            if force_reindex:
                result = indexing_service.reindex_document(document)
            else:
                result = indexing_service.index_document(document)
            
            # Обновляем объект документа из БД, чтобы получить актуальный chunks_count
            document.refresh_from_db()
            
            return Response({
                'success': True,
                'result': result,
                'document': {
                    'id': str(document.id),
                    'title': document.title,
                    'is_indexed': document.is_indexed,
                    'chunks_count': document.chunks_count,
                    'indexed_at': document.indexed_at.isoformat() if document.indexed_at else None,
                },
            }, status=status.HTTP_200_OK)
            
        except KnowledgeDocument.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Документ не найден'
            }, status=status.HTTP_404_NOT_FOUND)
        except RAGIndexingError as e:
            return Response({
                'success': False,
                'error': f'Ошибка индексации: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='unindex')
    def unindex(self, request, pk=None):
        """
        POST /api/ai_assistant/knowledge_documents/{id}/unindex/
        Деиндексировать документ (удалить chunks)
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        try:
            document = queryset.get(id=pk)
            
            embeddings_service, _ = get_rag_services()
            indexing_service = RAGIndexingService(
                embeddings_service=embeddings_service,
                chunk_size=RAG_CHUNK_SIZE,
                chunk_overlap=RAG_CHUNK_OVERLAP,
            )
            
            indexing_service.delete_document_index(document)
            
            return Response({
                'success': True,
                'message': 'Документ деиндексирован',
                'document': {
                    'id': str(document.id),
                    'title': document.title,
                    'is_indexed': document.is_indexed,
                    'chunks_count': document.chunks_count,
                },
            }, status=status.HTTP_200_OK)
            
        except KnowledgeDocument.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Документ не найден'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'], url_path='download')
    def download_file(self, request, pk=None):
        """
        GET /api/ai_assistant/knowledge_documents/{id}/download/
        Скачать файл документа
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        try:
            document = queryset.get(id=pk)
            
            if not document.file:
                return Response({
                    'success': False,
                    'error': 'У документа нет файла'
                }, status=status.HTTP_404_NOT_FOUND)
            
            try:
                file_handle = document.file.open('rb')
                filename = document.file.name.split('/')[-1]
                response = FileResponse(file_handle, as_attachment=True, filename=filename)
                return response
            except Exception as e:
                logger.error(f"Ошибка открытия файла документа {document.id}: {e}")
                return Response({
                    'success': False,
                    'error': f'Ошибка открытия файла: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except KnowledgeDocument.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Документ не найден'
            }, status=status.HTTP_404_NOT_FOUND)
