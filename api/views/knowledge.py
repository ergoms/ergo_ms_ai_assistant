import json
import logging

from django.http import HttpResponseRedirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from ..permissions import CanViewAiAssistant
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from src.core.utils.mixins import MediaApiFileMixin, SwaggerSafeMixin, validate_media_path
from src.core.utils.media_signing import get_signed_media_url
from ..file_uploads import assign_knowledge_file
from ..media_storage import parse_localized_document, signed_url_from_field
from ..models import KnowledgeDocument
from ..rag import (
    RAGIndexingService,
    DocumentParserService,
    DocumentParseError,
    RAGIndexingError,
)
from ..settings import (
    RAG_CHUNK_SIZE,
    RAG_CHUNK_OVERLAP,
)
from .helpers import _get_rag_services

logger = logging.getLogger(__name__)

class KnowledgeDocumentViewSet(MediaApiFileMixin, ViewSet, SwaggerSafeMixin):
    """
    ViewSet для управления документами базы знаний RAG
    
    Поддерживает:
    - Загрузку через media_api (file_path) или multipart fallback
    - Создание документов из текста через JSON
    - Автоматическое извлечение текста из файлов при индексации
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def list(self, request):
        """
        GET /api/ai_assistant/knowledge_documents/
        Получить список документов пользователя
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(
            user=user,
            corpus=KnowledgeDocument.CORPUS_USER,
        )
        queryset = self.get_safe_queryset(queryset)
        
        documents = []
        for doc in queryset.order_by('-created_at'):
            # Определяем размер файла
            file_size = None
            if doc.file:
                try:
                    file_size = doc.file.size
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
        
        Поддерживает:
        1. Загрузка файла через media_api:
           - file_path: путь в media_api
           - original_filename: исходное имя (опционально)
           - title, source, metadata, index_immediately
        2. multipart fallback: file
        3. Создание из текста (JSON): title + content
        """
        user = self.get_safe_user()
        
        title = request.data.get('title')
        uploaded_file, file_path = self.get_file_or_path('file')
        original_filename = request.data.get('original_filename') or (
            uploaded_file.name if uploaded_file else (file_path.rsplit('/', 1)[-1] if file_path else '')
        )
        content = request.data.get('content')
        source = request.data.get('source', '')
        metadata = request.data.get('metadata', {})
        index_immediately = request.data.get('index_immediately', False)
        if isinstance(index_immediately, str):
            index_immediately = index_immediately.lower() in ('true', '1', 'yes')
        
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
        
        if not uploaded_file and not file_path and not content:
            return Response({
                'success': False,
                'error': 'Не указаны ни файл, ни текстовое содержимое. Укажите file_path, file или content'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            file_type = None
            extracted_content = None
            
            if uploaded_file or file_path:
                file_type = DocumentParserService.get_file_type(original_filename)
                if index_immediately:
                    try:
                        if file_path:
                            extracted_content, detected_type = parse_localized_document(
                                file_path, filename=original_filename
                            )
                            file_type = detected_type
                        else:
                            from io import BytesIO
                            file_obj = BytesIO(uploaded_file.read())
                            extracted_content, detected_type = DocumentParserService.parse_document(
                                file_obj=file_obj,
                                filename=uploaded_file.name
                            )
                            file_type = detected_type
                            uploaded_file.seek(0)
                    except DocumentParseError as e:
                        logger.warning(f"Не удалось извлечь текст из файла сразу: {e}")
            
            final_content = extracted_content or content
            
            document = KnowledgeDocument.objects.create(
                user=user,
                corpus=KnowledgeDocument.CORPUS_USER,
                title=title,
                content=final_content,
                source=source or original_filename,
                metadata=metadata,
                file_type=file_type,
            )
            
            if uploaded_file or file_path:
                assign_knowledge_file(document, file=uploaded_file, file_path=file_path)
            
            indexing_result = None
            if index_immediately:
                try:
                    embeddings_service, _ = _get_rag_services()
                    indexing_service = RAGIndexingService(
                        embeddings_service=embeddings_service,
                        chunk_size=RAG_CHUNK_SIZE,
                        chunk_overlap=RAG_CHUNK_OVERLAP,
                    )
                    indexing_result = indexing_service.index_document(document)
                    document.refresh_from_db()
                except Exception as e:
                    logger.error(f"Ошибка индексации документа {document.id}: {e}", exc_info=True)
            
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
        queryset = KnowledgeDocument.objects.filter(
            user=user,
            corpus=KnowledgeDocument.CORPUS_USER,
        )
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
            
            file_info = None
            if document.file:
                try:
                    file_info = {
                        'name': document.file.name.split('/')[-1],
                        'size': document.file.size,
                        'url': signed_url_from_field(document.file),
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
        queryset = KnowledgeDocument.objects.filter(
            user=user,
            corpus=KnowledgeDocument.CORPUS_USER,
        )
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
        queryset = KnowledgeDocument.objects.filter(
            user=user,
            corpus=KnowledgeDocument.CORPUS_USER,
        )
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
        queryset = KnowledgeDocument.objects.filter(
            user=user,
            corpus=KnowledgeDocument.CORPUS_USER,
        )
        queryset = self.get_safe_queryset(queryset)
        
        force_reindex = request.data.get('force', False)
        
        try:
            document = queryset.get(id=pk)
            
            embeddings_service, _ = _get_rag_services()
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
        queryset = KnowledgeDocument.objects.filter(
            user=user,
            corpus=KnowledgeDocument.CORPUS_USER,
        )
        queryset = self.get_safe_queryset(queryset)
        
        try:
            document = queryset.get(id=pk)
            
            embeddings_service, _ = _get_rag_services()
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
        Редирект на подписанный URL media_api.
        """
        user = self.get_safe_user()
        queryset = KnowledgeDocument.objects.filter(
            user=user,
            corpus=KnowledgeDocument.CORPUS_USER,
        )
        queryset = self.get_safe_queryset(queryset)
        
        try:
            document = queryset.get(id=pk)
            
            if not document.file:
                return Response({
                    'success': False,
                    'error': 'У документа нет файла'
                }, status=status.HTTP_404_NOT_FOUND)
            
            url = signed_url_from_field(document.file)
            if not url:
                return Response({
                    'success': False,
                    'error': 'Не удалось сформировать ссылку на файл'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return HttpResponseRedirect(url)
            
        except KnowledgeDocument.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Документ не найден'
            }, status=status.HTTP_404_NOT_FOUND)


class GeneratedDocumentDownloadView(SwaggerSafeMixin, APIView):
    """
    GET /api/ai_assistant/documents/download/<path:file_path>
    Редирект на подписанный URL сгенерированного документа в media_api.
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]

    @staticmethod
    def _user_owns_storage_path(user, storage_path: str) -> bool:
        norm = storage_path.replace('\\', '/')
        user_prefix = f'user_{user.pk}/'
        if user_prefix in norm:
            return True
        for doc in KnowledgeDocument.objects.filter(
            user=user,
            corpus=KnowledgeDocument.CORPUS_USER,
        ).only('file', 'metadata'):
            meta_path = (doc.metadata or {}).get('storage_path') or (doc.metadata or {}).get('file_path', '')
            if meta_path and meta_path.replace('\\', '/') == norm:
                return True
            if doc.file and doc.file.name.replace('\\', '/') == norm:
                return True
        return False
    
    def get(self, request, file_path):
        from urllib.parse import unquote

        if self.is_swagger_fake_view():
            return Response({'success': True})

        decoded_path = unquote(file_path).replace('\\', '/')
        try:
            storage_path = validate_media_path(decoded_path, 'file')
        except Exception:
            return Response({
                'success': False,
                'error': 'Неверный путь к файлу'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = self.get_safe_user()
        if user is None or not self._user_owns_storage_path(user, storage_path):
            return Response({
                'success': False,
                'error': 'Нет доступа к файлу'
            }, status=status.HTTP_403_FORBIDDEN)

        url = get_signed_media_url(storage_path)
        if not url:
            return Response({
                'success': False,
                'error': 'Не удалось сформировать ссылку на файл'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return HttpResponseRedirect(url)

