"""
Сервис для поиска релевантных документов в RAG системе.
Использует pgvector (косинусное расстояние) в PostgreSQL.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.db.models import Q, QuerySet

from pgvector.django import CosineDistance

from ..assistant_role import assistant_is_admin
from ..models import KnowledgeDocument, KnowledgeChunk
from ..ownership import owner_public_id
from .audience import AUDIENCE_ADMIN
from .embeddings import OllamaEmbeddingsService, EmbeddingsError

logger = logging.getLogger(__name__)


class RAGRetrievalError(Exception):
    """Общее исключение для ошибок retrieval в RAG."""
    pass


@dataclass(frozen=True)
class RetrievalScope:
    """Область поиска chunks."""

    document_ids: Optional[List[str]] = None
    include_system: bool = False
    system_only: bool = False
    user: Optional[Any] = None
    limit: Optional[int] = None


class RAGRetrievalService:
    """
    Сервис для поиска релевантных chunks документов по запросу пользователя.
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

    def _base_chunks_query(self) -> QuerySet:
        return KnowledgeChunk.objects.select_related('document').filter(
            document__is_indexed=True,
            embedding_model=self.embeddings_service._model,
        )

    def _system_corpus_visibility_q(self, user) -> Q | None:
        """Сужает системный корпус по снимку прав. None — все пакеты (админ)."""
        try:
            from src.core.utils.knowledge_pack import visible_knowledge_owners

            owners = visible_knowledge_owners(user)
        except Exception:
            logger.warning(
                'Не удалось получить видимые пакеты справки, чанки с pack_owner скрыты',
                exc_info=True,
            )
            return (
                ~Q(document__metadata__has_key='pack_owner')
                | Q(document__metadata__pack_owner='')
            )
        if owners is None:
            return None
        return (
            ~Q(document__metadata__has_key='pack_owner')
            | Q(document__metadata__pack_owner='')
            | Q(document__metadata__pack_owner__in=sorted(owners))
        )

    def _system_corpus_audience_q(self, user) -> Q | None:
        """Скрывает audience=admin у не-админа. None — без фильтра."""
        if assistant_is_admin(user):
            return None
        return ~Q(document__metadata__audience=AUDIENCE_ADMIN)

    def _apply_scope_filters(
        self,
        chunks_query: QuerySet,
        *,
        user: Optional[Any] = None,
        document_ids: Optional[List[str]] = None,
        include_system: bool = False,
        system_only: bool = False,
    ) -> QuerySet:
        visibility = None
        audience = None
        if system_only or include_system:
            visibility = self._system_corpus_visibility_q(user)
            audience = self._system_corpus_audience_q(user)

        if document_ids:
            return chunks_query.filter(document_id__in=document_ids)
        if system_only:
            queryset = chunks_query.filter(
                document__corpus=KnowledgeDocument.CORPUS_SYSTEM,
            )
            if visibility is not None:
                queryset = queryset.filter(visibility)
            if audience is not None:
                queryset = queryset.filter(audience)
            return queryset
        if include_system and user is not None:
            system_q = Q(document__corpus=KnowledgeDocument.CORPUS_SYSTEM)
            if visibility is not None:
                system_q &= visibility
            if audience is not None:
                system_q &= audience
            return chunks_query.filter(
                system_q
                | Q(
                    document__user_public_id=owner_public_id(user),
                    document__corpus=KnowledgeDocument.CORPUS_USER,
                )
            )
        if include_system and user is None:
            queryset = chunks_query.filter(
                document__corpus=KnowledgeDocument.CORPUS_SYSTEM,
            )
            if visibility is not None:
                queryset = queryset.filter(visibility)
            if audience is not None:
                queryset = queryset.filter(audience)
            return queryset
        if user is not None:
            return chunks_query.filter(
                document__user_public_id=owner_public_id(user),
                document__corpus=KnowledgeDocument.CORPUS_USER,
            )
        return chunks_query

    def _rows_from_queryset(
        self,
        queryset: QuerySet,
        *,
        limit: int,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for chunk in queryset[:limit]:
            distance = getattr(chunk, 'distance', None)
            similarity = 1.0 - float(distance) if distance is not None else 0.0
            if similarity < self.similarity_threshold:
                continue
            results.append({
                'chunk_id': str(chunk.id),
                'document_id': str(chunk.document.id),
                'document_title': chunk.document.title,
                'document_source': chunk.document.source or '',
                'document_corpus': chunk.document.corpus,
                'content': chunk.content,
                'chunk_index': chunk.chunk_index,
                'similarity': similarity,
                'metadata': chunk.metadata,
                'document_metadata': chunk.document.metadata,
            })
        return results

    def retrieve_with_embedding(
        self,
        query_embedding: List[float],
        *,
        user: Optional[Any] = None,
        document_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_system: bool = False,
        system_only: bool = False,
    ) -> List[Dict[str, Any]]:
        if not query_embedding:
            raise RAGRetrievalError('Embedding запроса не может быть пустым')

        limit = limit or self.top_k
        chunks_query = self._base_chunks_query()
        chunks_query = self._apply_scope_filters(
            chunks_query,
            user=user,
            document_ids=document_ids,
            include_system=include_system,
            system_only=system_only,
        )
        chunks_query = chunks_query.annotate(
            distance=CosineDistance('embedding', query_embedding),
        ).order_by('distance')

        results = self._rows_from_queryset(chunks_query, limit=limit)
        logger.info(
            'Найдено %s релевантных chunks (pgvector, limit=%s)',
            len(results),
            limit,
        )
        return results

    def retrieve_relevant_chunks(
        self,
        query: str,
        user: Optional[Any] = None,
        document_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_system: bool = False,
        system_only: bool = False,
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            raise RAGRetrievalError('Запрос не может быть пустым')

        try:
            query_embedding = self.embeddings_service.generate_embedding(query.strip())
        except EmbeddingsError as exc:
            raise RAGRetrievalError(f'Ошибка генерации embedding для запроса: {exc}') from exc

        return self.retrieve_with_embedding(
            query_embedding,
            user=user,
            document_ids=document_ids,
            limit=limit,
            include_system=include_system,
            system_only=system_only,
        )

    def retrieve_multi_scope(
        self,
        query: str,
        scopes: Sequence[RetrievalScope],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Один embed на запрос, несколько областей поиска.
        Возвращает (merged_context_chunks, all_chunks).
        """
        if not query or not query.strip():
            raise RAGRetrievalError('Запрос не может быть пустым')
        if not scopes:
            return [], []

        try:
            query_embedding = self.embeddings_service.generate_embedding(query.strip())
        except EmbeddingsError as exc:
            raise RAGRetrievalError(f'Ошибка генерации embedding для запроса: {exc}') from exc

        all_chunks: List[Dict[str, Any]] = []
        seen_chunk_ids: set[str] = set()

        for scope in scopes:
            limit = scope.limit or self.top_k
            scope_chunks = self.retrieve_with_embedding(
                query_embedding,
                user=scope.user,
                document_ids=scope.document_ids,
                limit=limit,
                include_system=scope.include_system,
                system_only=scope.system_only,
            )
            for chunk in scope_chunks:
                chunk_id = chunk['chunk_id']
                if chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk_id)
                all_chunks.append(chunk)

        all_chunks.sort(key=lambda item: item['similarity'], reverse=True)
        return all_chunks, all_chunks

    def build_context_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        max_context_length: Optional[int] = None,
    ) -> str:
        if not chunks:
            return ''

        context_parts = []
        current_length = 0

        for chunk in chunks:
            source = chunk.get('document_source') or ''
            source_part = f' ({source})' if source else ''
            chunk_text = (
                f"[Документ: {chunk['document_title']}{source_part}]\n"
                f"{chunk['content']}\n\n"
            )
            chunk_length = len(chunk_text)

            if max_context_length and (current_length + chunk_length) > max_context_length:
                remaining = max_context_length - current_length
                if remaining > 100:
                    chunk_text = chunk_text[:remaining] + '...\n\n'
                    context_parts.append(chunk_text)
                break

            context_parts.append(chunk_text)
            current_length += chunk_length

        return ''.join(context_parts).strip()

    def retrieve_and_build_context(
        self,
        query: str,
        user: Optional[Any] = None,
        document_ids: Optional[List[str]] = None,
        max_context_length: Optional[int] = 4000,
        include_system: bool = False,
        system_only: bool = False,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        chunks = self.retrieve_relevant_chunks(
            query,
            user=user,
            document_ids=document_ids,
            include_system=include_system,
            system_only=system_only,
        )
        context = self.build_context_from_chunks(chunks, max_context_length=max_context_length)
        return context, chunks

    def retrieve_multi_scope_context(
        self,
        query: str,
        scopes: Sequence[RetrievalScope],
        *,
        max_context_length: Optional[int] = 4000,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        _, chunks = self.retrieve_multi_scope(query, scopes)
        context = self.build_context_from_chunks(chunks, max_context_length=max_context_length)
        return context, chunks
