"""
Сервис для индексации документов в RAG системе
Разбивает документы на chunks и создает embeddings
"""
import logging
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db import transaction

from ..models import KnowledgeDocument, KnowledgeChunk
from .chonkie_chunking import split_text_with_chonkie
from .embeddings import OllamaEmbeddingsService, EmbeddingsError
from .parser import DocumentParseError

logger = logging.getLogger(__name__)


class RAGIndexingError(Exception):
    """Общее исключение для ошибок индексации RAG."""
    pass


class RAGIndexingService:
    """
    Сервис для индексации документов в векторную базу знаний
    
    Функционал:
    - Разбиение документов на chunks через chonkie
    - Генерация embeddings для каждого chunk
    - Сохранение в базу данных
    """
    
    def __init__(
        self,
        embeddings_service: OllamaEmbeddingsService,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        Инициализация сервиса индексации
        
        Args:
            embeddings_service: Сервис для генерации embeddings
            chunk_size: Максимальный размер chunk (tokenizer character у chonkie)
            chunk_overlap: Размер перекрытия между chunks (OverlapRefinery)
        """
        self.embeddings_service = embeddings_service
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def _split_text_into_chunks(
        self,
        text: str,
        *,
        file_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Разбивает текст на chunks через chonkie."""
        try:
            return split_text_with_chonkie(
                text,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                file_type=file_type,
            )
        except Exception as exc:
            raise RAGIndexingError(f'Ошибка разбиения на chunks: {exc}') from exc
    
    def index_document(
        self,
        document: KnowledgeDocument,
        force_reindex: bool = False,
    ) -> Dict[str, Any]:
        """
        Индексирует документ: извлекает текст (если есть файл), разбивает на chunks и создает embeddings
        
        Args:
            document: Документ для индексации
            force_reindex: Если True, переиндексирует документ даже если он уже индексирован
            
        Returns:
            Словарь с результатами индексации:
            {
                "success": bool,
                "chunks_created": int,
                "chunks_updated": int,
                "chunks_deleted": int,
                "error": str (если была ошибка)
            }
            
        Raises:
            RAGIndexingError: При ошибке индексации
        """
        if document.is_indexed and not force_reindex:
            logger.debug('Документ %s уже индексирован, пропускаем', document.id)
            return {
                "success": True,
                "chunks_created": 0,
                "chunks_updated": 0,
                "chunks_deleted": 0,
                "message": "Документ уже индексирован",
            }
        
        try:
            # Если есть файл, но нет контента - извлекаем текст из файла через media_api
            text_content = document.content
            if document.file and not text_content:
                try:
                    logger.debug(
                        'Извлекаем текст из файла %s для документа %s',
                        document.file.name,
                        document.id,
                    )
                    from ..media_storage import parse_localized_document

                    text_content, file_type = parse_localized_document(
                        document.file.name,
                        filename=document.file.name.split('/')[-1],
                    )
                    
                    document.content = text_content
                    if not document.file_type:
                        document.file_type = file_type
                    document.save(update_fields=['content', 'file_type'])
                    
                    logger.debug(
                        'Извлечён текст из файла (тип: %s, длина: %s символов)',
                        file_type,
                        len(text_content),
                    )
                except DocumentParseError as e:
                    raise RAGIndexingError(f"Ошибка парсинга файла: {e}") from e
                except Exception as e:
                    raise RAGIndexingError(f"Неожиданная ошибка при извлечении текста из файла: {e}") from e
            
            if not text_content or not text_content.strip():
                raise RAGIndexingError(
                    "Документ не содержит текстового контента. "
                    "Убедитесь, что указан текст или загружен файл с текстом."
                )
            
            # Разбиваем текст на chunks (chonkie)
            chunks_data = self._split_text_into_chunks(
                text_content,
                file_type=document.file_type,
            )
            
            if not chunks_data:
                raise RAGIndexingError("Не удалось разбить документ на chunks (возможно, документ пуст)")
            
            logger.debug('Документ %s разбит на %s chunks', document.id, len(chunks_data))
            
            # Генерируем embeddings для всех chunks батчем
            texts_for_embedding = [chunk["content"] for chunk in chunks_data]
            
            try:
                embeddings_list = self.embeddings_service.generate_embeddings_batch(texts_for_embedding)
            except EmbeddingsError as e:
                raise RAGIndexingError(f"Ошибка генерации embeddings: {e}") from e
            
            if len(embeddings_list) != len(chunks_data):
                logger.warning(
                    'Количество embeddings (%s) не совпадает с количеством chunks (%s)',
                    len(embeddings_list),
                    len(chunks_data),
                )
                # Обрезаем или дополняем до нужного количества
                if len(embeddings_list) < len(chunks_data):
                    raise RAGIndexingError(
                        f"Получено недостаточно embeddings: {len(embeddings_list)} из {len(chunks_data)}"
                    )
                embeddings_list = embeddings_list[:len(chunks_data)]
            
            # Сохраняем chunks в базу данных в транзакции
            with transaction.atomic():
                chunks_created = 0
                chunks_updated = 0
                chunks_deleted = 0
                
                # Если переиндексируем, удаляем старые chunks
                if force_reindex:
                    old_chunks_count = document.chunks.count()
                    if old_chunks_count > 0:
                        document.chunks.all().delete()
                        chunks_deleted = old_chunks_count
                        logger.debug(
                            'Удалили %s старых chunks документа %s',
                            chunks_deleted,
                            document.id,
                        )
                
                # Создаем новые chunks
                embedding_model = self.embeddings_service._model
                
                for i, (chunk_data, embedding) in enumerate(zip(chunks_data, embeddings_list)):
                    chunk, created = KnowledgeChunk.objects.update_or_create(
                        document=document,
                        chunk_index=i,
                        defaults={
                            "content": chunk_data["content"],
                            "start_char": chunk_data["start_char"],
                            "end_char": chunk_data["end_char"],
                            "embedding": embedding,
                            "embedding_model": embedding_model,
                        }
                    )
                    
                    if created:
                        chunks_created += 1
                    else:
                        chunks_updated += 1
                
                # Обновляем статус индексации документа
                document.is_indexed = True
                document.indexed_at = timezone.now()
                document.save(update_fields=["is_indexed", "indexed_at"])
                
                logger.debug(
                    'Проиндексирован документ %s: создано %s, обновлено %s, удалено %s chunks',
                    document.id,
                    chunks_created,
                    chunks_updated,
                    chunks_deleted,
                )
                
                return {
                    "success": True,
                    "chunks_created": chunks_created,
                    "chunks_updated": chunks_updated,
                    "chunks_deleted": chunks_deleted,
                    "total_chunks": len(chunks_data),
                }
                
        except RAGIndexingError:
            raise
        except Exception as e:
            logger.error(
                'Неожиданная ошибка при индексации документа %s: %s',
                document.id,
                e,
                exc_info=True,
            )
            raise RAGIndexingError(f"Ошибка индексации: {e}") from e
    
    def reindex_document(self, document: KnowledgeDocument) -> Dict[str, Any]:
        """
        Переиндексирует документ (удаляет старые chunks и создает новые)
        
        Args:
            document: Документ для переиндексации
            
        Returns:
            Результаты индексации (см. index_document)
        """
        return self.index_document(document, force_reindex=True)
    
    def delete_document_index(self, document: KnowledgeDocument) -> None:
        """
        Удаляет все chunks документа (деиндексирует)
        
        Args:
            document: Документ для деиндексации
        """
        with transaction.atomic():
            chunks_count = document.chunks.count()
            document.chunks.all().delete()
            document.is_indexed = False
            document.indexed_at = None
            document.save(update_fields=["is_indexed", "indexed_at"])
            logger.debug(
                'Деиндексирован документ %s: удалено %s chunks',
                document.id,
                chunks_count,
            )

