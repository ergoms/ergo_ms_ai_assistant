"""
Сервис для поиска релевантных документов в RAG системе.
Поддерживает: векторный поиск, BM25, гибридный RRF, parent-document retrieval,
multi-query расширение, cross-encoder re-ranking через Ollama.
"""
import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from ..models import KnowledgeDocument, KnowledgeChunk
from .embeddings import OllamaEmbeddingsService, EmbeddingsError

logger = logging.getLogger(__name__)


class RAGRetrievalError(Exception):
    """Общее исключение для ошибок retrieval в RAG."""
    pass


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Вычисляет косинусное сходство между двумя векторами."""
    if len(vec1) != len(vec2):
        raise ValueError(f"Векторы должны иметь одинаковую длину: {len(vec1)} != {len(vec2)}")
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(a * a for a in vec2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


class RAGRetrievalService:
    """
    Сервис для поиска релевантных chunks документов по запросу пользователя.
    Использует векторный поиск по косинусному сходству.
    """

    def __init__(
        self,
        embeddings_service: OllamaEmbeddingsService,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ):
        self.embeddings_service = embeddings_service
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def retrieve_relevant_chunks(
        self,
        query: str,
        user: Optional[Any] = None,
        document_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Находит наиболее релевантные chunks для запроса пользователя.
        Возвращает список словарей отсортированных по убыванию схожести.
        """
        if not query or not query.strip():
            raise RAGRetrievalError("Запрос не может быть пустым")

        try:
            query_embedding = self.embeddings_service.generate_embedding(query.strip())
            chunks_query = KnowledgeChunk.objects.select_related('document', 'parent_chunk').filter(
                document__is_indexed=True,
                embedding_model=self.embeddings_service._model,
            )
            if user is not None:
                chunks_query = chunks_query.filter(document__user=user)
            if document_ids:
                chunks_query = chunks_query.filter(document_id__in=document_ids)

            results = []
            for chunk in chunks_query:
                try:
                    similarity = cosine_similarity(query_embedding, chunk.embedding)
                    if similarity >= self.similarity_threshold:
                        results.append(self._chunk_to_dict(chunk, similarity))
                except Exception as e:
                    logger.warning(f"Ошибка при вычислении схожести для chunk {chunk.id}: {e}")
                    continue

            results.sort(key=lambda x: x["similarity"], reverse=True)
            limit = limit or self.top_k
            results = results[:limit]

            logger.info(
                f"Найдено {len(results)} релевантных chunks для запроса "
                f"'{query[:50]}...' (проверено {chunks_query.count()} chunks)"
            )
            return results

        except EmbeddingsError as e:
            raise RAGRetrievalError(f"Ошибка генерации embedding для запроса: {e}") from e
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске релевантных chunks: {e}", exc_info=True)
            raise RAGRetrievalError(f"Ошибка поиска: {e}") from e

    def _chunk_to_dict(self, chunk: KnowledgeChunk, similarity: float) -> Dict[str, Any]:
        """Конвертирует ORM-объект chunk в словарь."""
        # Если есть parent_chunk — используем его контент для LLM
        display_content = chunk.content
        if chunk.parent_chunk_id and chunk.parent_chunk:
            display_content = chunk.parent_chunk.content

        return {
            "chunk_id": str(chunk.id),
            "document_id": str(chunk.document.id),
            "document_title": chunk.document.title,
            "content": display_content,
            "child_content": chunk.content,  # оригинальный маленький chunk
            "chunk_index": chunk.chunk_index,
            "similarity": similarity,
            "metadata": chunk.metadata,
            "document_metadata": chunk.document.metadata,
        }

    def build_context_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        max_context_length: Optional[int] = None,
    ) -> str:
        """Формирует контекст из найденных chunks для передачи в LLM."""
        if not chunks:
            return ""

        context_parts = []
        current_length = 0

        for chunk in chunks:
            chunk_text = f"[Документ: {chunk['document_title']}]\n{chunk['content']}\n\n"
            chunk_length = len(chunk_text)

            if max_context_length and (current_length + chunk_length) > max_context_length:
                remaining = max_context_length - current_length
                if remaining > 100:
                    chunk_text = chunk_text[:remaining] + "...\n\n"
                    context_parts.append(chunk_text)
                break

            context_parts.append(chunk_text)
            current_length += chunk_length

        return "".join(context_parts).strip()

    def retrieve_and_build_context(
        self,
        query: str,
        user: Optional[Any] = None,
        document_ids: Optional[List[str]] = None,
        max_context_length: Optional[int] = 4000,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Комбинированный метод: находит релевантные chunks и формирует контекст."""
        chunks = self.retrieve_relevant_chunks(query, user=user, document_ids=document_ids)
        context = self.build_context_from_chunks(chunks, max_context_length=max_context_length)
        return context, chunks


class HybridRAGRetrievalService(RAGRetrievalService):
    """
    Расширенный сервис RAG с гибридным поиском (BM25 + семантика, RRF fusion),
    multi-query расширением и cross-encoder re-ranking через Ollama.
    """

    def __init__(
        self,
        embeddings_service: OllamaEmbeddingsService,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        rerank_top_n: int = 20,
        reranking_enabled: bool = True,
        multi_query_enabled: bool = True,
        llm_client: Optional[Any] = None,
    ):
        super().__init__(embeddings_service, top_k, similarity_threshold)
        self.rerank_top_n = rerank_top_n
        self.reranking_enabled = reranking_enabled
        self.multi_query_enabled = multi_query_enabled
        self.llm_client = llm_client  # используется для multi-query и re-ranking

    def _bm25_search(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> List[Tuple[Dict[str, Any], float]]:
        """BM25-ранжирование по child_content chunk'ов."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.warning("rank-bm25 не установлен, BM25 поиск недоступен")
            return [(c, 0.0) for c in chunks]

        if not chunks:
            return []

        # Токенизация — простое разбиение по пробелам (lowercase)
        tokenized_corpus = [
            (c.get("child_content") or c.get("content", "")).lower().split()
            for c in chunks
        ]
        bm25 = BM25Okapi(tokenized_corpus)
        query_tokens = query.lower().split()
        scores = bm25.get_scores(query_tokens)
        return list(zip(chunks, scores.tolist()))

    def _rrf_fusion(
        self,
        bm25_results: List[Tuple[Dict[str, Any], float]],
        semantic_results: List[Dict[str, Any]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion:
        score_rrf(doc) = 1/(k + rank_bm25) + 1/(k + rank_semantic)
        """
        # Строим словарь chunk_id → позиция в BM25
        sorted_bm25 = sorted(bm25_results, key=lambda x: x[1], reverse=True)
        bm25_rank = {item[0]["chunk_id"]: i for i, item in enumerate(sorted_bm25)}

        # Позиция в семантическом поиске
        semantic_rank = {item["chunk_id"]: i for i, item in enumerate(semantic_results)}

        # Объединяем все уникальные chunk_id
        all_ids = set(bm25_rank) | set(semantic_rank)

        # Словарь chunk_id → chunk dict
        chunk_map = {item[0]["chunk_id"]: item[0] for item in bm25_results}
        for item in semantic_results:
            chunk_map[item["chunk_id"]] = item

        scores = {}
        for cid in all_ids:
            rank_b = bm25_rank.get(cid, len(bm25_rank))
            rank_s = semantic_rank.get(cid, len(semantic_results))
            scores[cid] = 1.0 / (k + rank_b) + 1.0 / (k + rank_s)

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        result = []
        for cid in sorted_ids:
            chunk = chunk_map.get(cid)
            if chunk:
                chunk = dict(chunk)
                chunk["similarity"] = scores[cid]
                result.append(chunk)
        return result

    def expand_query(self, query: str) -> List[str]:
        """
        Генерирует 3 перефразировки запроса через Ollama для multi-query retrieval.
        При ошибке возвращает только исходный запрос.
        """
        if not self.llm_client:
            return [query]
        try:
            prompt = (
                f"Generate 3 alternative phrasings of the following query to improve document retrieval. "
                f"Return ONLY a JSON array of strings, no explanation.\n"
                f"Query: {query}\n"
                f"Example output: [\"variant 1\", \"variant 2\", \"variant 3\"]"
            )
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages, temperature=0.3, format="json", num_predict=200)
            try:
                variants = json.loads(response)
                if isinstance(variants, list):
                    return [query] + [str(v) for v in variants[:3] if v]
            except (json.JSONDecodeError, ValueError):
                pass
        except Exception as e:
            logger.warning(f"Ошибка при расширении запроса: {e}")
        return [query]

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Cross-encoder re-ranking через Ollama structured output.
        Переранжирует top candidates и возвращает top_k.
        При ошибке возвращает исходный порядок.
        """
        if not self.llm_client or not candidates:
            return candidates[:top_k]

        try:
            # Формируем батчевый запрос на оценку релевантности
            chunks_text = "\n".join([
                f'Chunk {i} (id={c["chunk_id"]}): {(c.get("child_content") or c.get("content", ""))[:200]}'
                for i, c in enumerate(candidates)
            ])
            prompt = (
                f"Rate the relevance of each chunk to the query. "
                f"Return a JSON array of objects with fields 'chunk_id' and 'relevance' (0-10).\n\n"
                f"Query: {query}\n\n"
                f"Chunks:\n{chunks_text}\n\n"
                f"Return ONLY valid JSON array, e.g.: "
                f'[{{"chunk_id": "uuid1", "relevance": 8}}, {{"chunk_id": "uuid2", "relevance": 3}}]'
            )
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages, temperature=0, format="json", num_predict=500)

            scores_raw = json.loads(response)
            if not isinstance(scores_raw, list):
                return candidates[:top_k]

            # Строим словарь chunk_id → relevance
            relevance_map = {}
            for item in scores_raw:
                if isinstance(item, dict) and "chunk_id" in item and "relevance" in item:
                    try:
                        relevance_map[str(item["chunk_id"])] = float(item["relevance"])
                    except (ValueError, TypeError):
                        pass

            if not relevance_map:
                return candidates[:top_k]

            # Переранжируем
            reranked = sorted(
                candidates,
                key=lambda c: relevance_map.get(c["chunk_id"], 0.0),
                reverse=True
            )
            return reranked[:top_k]

        except Exception as e:
            logger.warning(f"Ошибка re-ranking, используем исходный порядок: {e}")
            return candidates[:top_k]

    def retrieve_relevant_chunks(
        self,
        query: str,
        user: Optional[Any] = None,
        document_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Гибридный поиск: BM25 + семантика → RRF → (multi-query) → (re-ranking).
        """
        if not query or not query.strip():
            raise RAGRetrievalError("Запрос не может быть пустым")

        try:
            # Получаем все проиндексированные chunks один раз
            chunks_query = KnowledgeChunk.objects.select_related('document', 'parent_chunk').filter(
                document__is_indexed=True,
                embedding_model=self.embeddings_service._model,
                parent_chunk__isnull=True,  # только дочерние или одиночные chunks
            )
            if user is not None:
                chunks_query = chunks_query.filter(document__user=user)
            if document_ids:
                chunks_query = chunks_query.filter(document_id__in=document_ids)

            all_chunks = list(chunks_query)
            if not all_chunks:
                return []

            # Multi-query expansion
            queries = [query]
            if self.multi_query_enabled and self.llm_client:
                queries = self.expand_query(query)

            # Семантический поиск по всем запросам
            candidate_set: Dict[str, Dict[str, Any]] = {}
            for q in queries:
                try:
                    q_embedding = self.embeddings_service.generate_embedding(q.strip())
                    for chunk in all_chunks:
                        try:
                            sim = cosine_similarity(q_embedding, chunk.embedding)
                            cid = str(chunk.id)
                            if cid not in candidate_set or sim > candidate_set[cid]["similarity"]:
                                d = self._chunk_to_dict(chunk, sim)
                                candidate_set[cid] = d
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"Ошибка семантического поиска для запроса '{q}': {e}")

            semantic_results = sorted(candidate_set.values(), key=lambda x: x["similarity"], reverse=True)

            # BM25 поиск (по первому запросу)
            all_dicts = [self._chunk_to_dict(c, 0.0) for c in all_chunks]
            bm25_results = self._bm25_search(query, all_dicts)

            # RRF fusion
            top_n = self.rerank_top_n
            fused = self._rrf_fusion(bm25_results, semantic_results, k=60)
            candidates = fused[:top_n]

            # Фильтр по threshold
            candidates = [c for c in candidates if c.get("similarity", 0) >= self.similarity_threshold]

            # Re-ranking
            final_limit = limit or self.top_k
            if self.reranking_enabled and self.llm_client and len(candidates) > final_limit:
                final = self.rerank(query, candidates, top_k=final_limit)
            else:
                final = candidates[:final_limit]

            logger.info(
                f"Гибридный поиск: запросов={len(queries)}, кандидатов={len(candidates)}, "
                f"итог={len(final)} для '{query[:50]}'"
            )
            return final

        except EmbeddingsError as e:
            raise RAGRetrievalError(f"Ошибка генерации embedding для запроса: {e}") from e
        except RAGRetrievalError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при гибридном поиске: {e}", exc_info=True)
            raise RAGRetrievalError(f"Ошибка поиска: {e}") from e
