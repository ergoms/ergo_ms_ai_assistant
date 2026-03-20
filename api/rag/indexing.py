"""
Сервис для индексации документов в RAG системе
Разбивает документы на chunks и создает embeddings
"""
import logging
from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db import transaction

from ..models import KnowledgeDocument, KnowledgeChunk
from .embeddings import OllamaEmbeddingsService, EmbeddingsError
from .parser import DocumentParserService, DocumentParseError

logger = logging.getLogger(__name__)


class RAGIndexingError(Exception):
    """Общее исключение для ошибок индексации RAG."""
    pass


class RAGIndexingService:
    """
    Сервис для индексации документов в векторную базу знаний.
    Поддерживает parent-document retrieval: большие родительские chunks для контекста,
    маленькие дочерние для точного поиска.
    """

    def __init__(
        self,
        embeddings_service: OllamaEmbeddingsService,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        parent_chunk_size: int = 1500,
        child_chunk_size: int = 200,
        use_parent_document: bool = True,
    ):
        """
        Инициализация сервиса индексации
        
        Args:
            embeddings_service: Сервис для генерации embeddings
            chunk_size: Максимальный размер chunk в символах (используется если use_parent_document=False)
            chunk_overlap: Размер перекрытия между chunks в символах
            parent_chunk_size: Размер родительского chunk (большой контекстный блок)
            child_chunk_size: Размер дочернего chunk (маленький для точного поиска)
            use_parent_document: Если True — использовать parent-document retrieval
        """
        self.embeddings_service = embeddings_service
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.parent_chunk_size = parent_chunk_size
        self.child_chunk_size = child_chunk_size
        self.use_parent_document = use_parent_document
    
    def _split_text_into_chunks(self, text: str) -> List[Dict[str, Any]]:
        """
        Разбивает текст на chunks
        
        Args:
            text: Текст для разбиения
            
        Returns:
            Список словарей с ключами: content, start_char, end_char
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        text_length = len(text)
        
        # Минимальный размер chunk (чтобы не создавать слишком мелкие chunks)
        min_chunk_size = max(50, self.chunk_size // 10)
        
        # Разбиваем текст на chunks с перекрытием
        start = 0
        chunk_index = 0
        
        while start < text_length:
            # Базовый конец chunk (по максимальному размеру)
            end = min(start + self.chunk_size, text_length)
            
            # Если не последний chunk и не конец текста, пытаемся разбить по границе предложения или слова
            if end < text_length:
                # Сначала ищем ближайшую границу предложения (ищем назад от конца chunk)
                # Увеличиваем область поиска для лучшего разбиения
                sentence_end = None
                search_start = max(start, end - min(300, self.chunk_size // 2))
                for i in range(end - 1, search_start - 1, -1):
                    if text[i] in '.!?\n':
                        sentence_end = i + 1
                        break
                
                # Если нашли границу предложения в пределах разумного, используем её
                # Уменьшаем минимальный порог для более агрессивного разбиения
                if sentence_end and sentence_end > start + min_chunk_size:
                    end = sentence_end
                else:
                    # Если не нашли границу предложения, ищем границу слова (пробел, перенос строки, табуляция)
                    word_end = None
                    search_start = max(start, end - min(150, self.chunk_size // 3))
                    for i in range(end - 1, search_start - 1, -1):
                        if text[i] in ' \n\t':
                            word_end = i + 1
                            break
                    
                    # Если нашли границу слова в пределах разумного, используем её
                    if word_end and word_end > start + min_chunk_size:
                        end = word_end
                    # Если не нашли ни границу предложения, ни слова, оставляем end как есть
                    # (это может произойти для очень длинных слов или строк без пробелов)
            
            chunk_content = text[start:end].strip()
            if chunk_content:
                chunks.append({
                    "content": chunk_content,
                    "start_char": start,
                    "end_char": end,
                    "chunk_index": chunk_index,
                })
            
            # Переходим к следующему chunk с учетом overlap
            # Вычисляем начальную позицию следующего chunk с учетом overlap
            next_start = end - self.chunk_overlap
            
            # Убеждаемся, что мы продвигаемся вперед (хотя бы на минимальный шаг)
            if next_start <= start:
                # Если overlap слишком большой, просто идем вперед минимум на половину chunk_size
                next_start = start + max(min_chunk_size, self.chunk_size - self.chunk_overlap)
            
            # Также ищем границу слова для начала следующего chunk (чтобы не начинать с середины слова)
            if next_start < text_length and next_start > 0:
                # Если мы не в начале текста и не на границе слова, ищем ближайшую границу слова вперед
                if text[next_start] not in ' \n\t':
                    # Ищем ближайший пробел или перенос строки вперед (увеличиваем область поиска)
                    for i in range(next_start, min(text_length, next_start + 100)):
                        if text[i] in ' \n\t':
                            next_start = i + 1
                            break
            
            start = next_start
            chunk_index += 1
            
            # Защита от бесконечного цикла
            if chunk_index > 10000:  # Увеличиваем лимит для больших документов
                logger.warning(f"Превышен лимит chunks (10000), останавливаем разбиение. Текст: {text[:100]}...")
                break
        
        return chunks
    
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
            logger.info(f"Документ {document.id} уже индексирован, пропускаем")
            return {
                "success": True,
                "chunks_created": 0,
                "chunks_updated": 0,
                "chunks_deleted": 0,
                "message": "Документ уже индексирован",
            }
        
        try:
            # Если есть файл, но нет контента - извлекаем текст из файла
            text_content = document.content
            if document.file and not text_content:
                try:
                    logger.info(f"Извлекаем текст из файла {document.file.name} для документа {document.id}")
                    file_path = document.file.path if hasattr(document.file, 'path') else None
                    text_content, file_type = DocumentParserService.parse_document(
                        file_path=file_path,
                        filename=document.file.name
                    )
                    
                    # Сохраняем извлеченный контент и тип файла
                    document.content = text_content
                    if not document.file_type:
                        document.file_type = file_type
                    document.save(update_fields=['content', 'file_type'])
                    
                    logger.info(f"Успешно извлечен текст из файла (тип: {file_type}, длина: {len(text_content)} символов)")
                except DocumentParseError as e:
                    raise RAGIndexingError(f"Ошибка парсинга файла: {e}") from e
                except Exception as e:
                    raise RAGIndexingError(f"Неожиданная ошибка при извлечении текста из файла: {e}") from e
            
            if not text_content or not text_content.strip():
                raise RAGIndexingError(
                    "Документ не содержит текстового контента. "
                    "Убедитесь, что указан текст или загружен файл с текстом."
                )
            
            if self.use_parent_document:
                return self._index_with_parent_document(document, text_content, force_reindex)
            else:
                return self._index_flat(document, text_content, force_reindex)

        except RAGIndexingError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при индексации документа {document.id}: {e}", exc_info=True)
            raise RAGIndexingError(f"Ошибка индексации: {e}") from e

    def _index_flat(self, document: KnowledgeDocument, text_content: str, force_reindex: bool) -> dict:
        """Стандартная плоская индексация без parent-document."""
        chunks_data = self._split_text_into_chunks(text_content)
        if not chunks_data:
            raise RAGIndexingError("Не удалось разбить документ на chunks (возможно, документ пуст)")

        logger.info(f"Разбили документ {document.id} на {len(chunks_data)} chunks (flat)")

        texts_for_embedding = [chunk["content"] for chunk in chunks_data]
        try:
            embeddings_list = self.embeddings_service.generate_embeddings_batch(texts_for_embedding)
        except EmbeddingsError as e:
            raise RAGIndexingError(f"Ошибка генерации embeddings: {e}") from e

        if len(embeddings_list) < len(chunks_data):
            raise RAGIndexingError(
                f"Получено недостаточно embeddings: {len(embeddings_list)} из {len(chunks_data)}"
            )
        embeddings_list = embeddings_list[:len(chunks_data)]

        with transaction.atomic():
            chunks_created = chunks_updated = chunks_deleted = 0
            if force_reindex:
                old = document.chunks.count()
                if old > 0:
                    document.chunks.all().delete()
                    chunks_deleted = old
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
                        "parent_chunk": None,
                    }
                )
                if created:
                    chunks_created += 1
                else:
                    chunks_updated += 1

            document.is_indexed = True
            document.indexed_at = timezone.now()
            document.save(update_fields=["is_indexed", "indexed_at"])

            logger.info(
                f"Проиндексирован документ {document.id} (flat): "
                f"создано {chunks_created}, обновлено {chunks_updated}, удалено {chunks_deleted}"
            )
            return {
                "success": True,
                "chunks_created": chunks_created,
                "chunks_updated": chunks_updated,
                "chunks_deleted": chunks_deleted,
                "total_chunks": len(chunks_data),
            }

    def _index_with_parent_document(self, document: KnowledgeDocument, text_content: str, force_reindex: bool) -> dict:
        """
        Parent-document retrieval индексация:
        - родительские chunks (большие) — для контекста LLM
        - дочерние chunks (маленькие) — для векторного поиска
        """
        # Временно меняем chunk_size для создания parent/child chunks
        orig_size = self.chunk_size
        orig_overlap = self.chunk_overlap

        # Родительские chunks
        self.chunk_size = self.parent_chunk_size
        self.chunk_overlap = max(50, self.parent_chunk_size // 10)
        parent_chunks_data = self._split_text_into_chunks(text_content)

        # Дочерние chunks
        self.chunk_size = self.child_chunk_size
        self.chunk_overlap = max(20, self.child_chunk_size // 5)
        child_chunks_data = self._split_text_into_chunks(text_content)

        self.chunk_size = orig_size
        self.chunk_overlap = orig_overlap

        if not child_chunks_data:
            raise RAGIndexingError("Не удалось разбить документ на дочерние chunks")

        # Генерируем embeddings только для дочерних chunks
        child_texts = [c["content"] for c in child_chunks_data]
        try:
            embeddings_list = self.embeddings_service.generate_embeddings_batch(child_texts)
        except EmbeddingsError as e:
            raise RAGIndexingError(f"Ошибка генерации embeddings: {e}") from e

        if len(embeddings_list) < len(child_chunks_data):
            raise RAGIndexingError(
                f"Получено недостаточно embeddings: {len(embeddings_list)} из {len(child_chunks_data)}"
            )
        embeddings_list = embeddings_list[:len(child_chunks_data)]

        with transaction.atomic():
            if force_reindex:
                old = document.chunks.count()
                if old > 0:
                    document.chunks.all().delete()

            embedding_model = self.embeddings_service._model
            chunks_created = 0

            # Создаём родительские chunks (без embedding — только для контекста)
            parent_orm_chunks = []
            for i, p_data in enumerate(parent_chunks_data):
                parent_chunk = KnowledgeChunk.objects.create(
                    document=document,
                    chunk_index=i,
                    content=p_data["content"],
                    start_char=p_data["start_char"],
                    end_char=p_data["end_char"],
                    embedding=[0.0],  # placeholder — не используется для поиска
                    embedding_model=embedding_model,
                    parent_chunk=None,
                    metadata={"is_parent": True},
                )
                parent_orm_chunks.append(parent_chunk)
                chunks_created += 1

            # Создаём дочерние chunks со ссылкой на родительский
            # Определяем родителя по перекрытию позиций
            for i, (c_data, embedding) in enumerate(zip(child_chunks_data, embeddings_list)):
                # Ищем родительский chunk, который максимально перекрывает дочерний
                parent = self._find_parent_chunk(
                    c_data["start_char"], c_data["end_char"], parent_orm_chunks, parent_chunks_data
                )
                KnowledgeChunk.objects.create(
                    document=document,
                    chunk_index=len(parent_chunks_data) + i,
                    content=c_data["content"],
                    start_char=c_data["start_char"],
                    end_char=c_data["end_char"],
                    embedding=embedding,
                    embedding_model=embedding_model,
                    parent_chunk=parent,
                    metadata={"is_child": True},
                )
                chunks_created += 1

            document.is_indexed = True
            document.indexed_at = timezone.now()
            document.save(update_fields=["is_indexed", "indexed_at"])

            logger.info(
                f"Проиндексирован документ {document.id} (parent-document): "
                f"родительских={len(parent_orm_chunks)}, дочерних={len(child_chunks_data)}"
            )
            return {
                "success": True,
                "chunks_created": chunks_created,
                "chunks_updated": 0,
                "chunks_deleted": 0,
                "total_chunks": chunks_created,
            }

    def _find_parent_chunk(self, start: int, end: int, parent_orm: list, parent_data: list):
        """Находит родительский chunk с максимальным перекрытием с дочерним диапазоном."""
        best_parent = None
        best_overlap = -1
        for orm_chunk, p_data in zip(parent_orm, parent_data):
            p_start = p_data["start_char"]
            p_end = p_data["end_char"]
            overlap = max(0, min(end, p_end) - max(start, p_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_parent = orm_chunk
        return best_parent

    def _index_document_inner(self, document, text_content, force_reindex):
        pass  # kept for compat
                
        except RAGIndexingError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при индексации документа {document.id}: {e}", exc_info=True)
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
            logger.info(f"Деиндексирован документ {document.id}: удалено {chunks_count} chunks")

