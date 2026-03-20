"""Lazy singletons for RAG embeddings + retrieval (keyed by base_url/model)."""

from __future__ import annotations

import logging
from typing import Any

from .assistant_settings import (
    AI_ASSISTANT_REQUEST_TIMEOUT,
    MULTI_QUERY_ENABLED,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDINGS_MODEL,
    RAG_ENABLED,
    RAG_MAX_CONTEXT_LENGTH,
    RAG_RERANK_TOP_N,
    RAG_SIMILARITY_THRESHOLD,
    RAG_TOP_K,
    RERANKING_ENABLED,
)

from .rag import (
    OllamaEmbeddingsService,
    RAGRetrievalError,
)
from .rag.retrieval import HybridRAGRetrievalService

logger = logging.getLogger(__name__)

_rag_config_key: tuple[str, str] | None = None
_rag_embeddings_service: OllamaEmbeddingsService | None = None
_rag_retrieval_service: HybridRAGRetrievalService | None = None


def get_rag_services(ollama_config: dict[str, Any] | None = None, llm_client: Any | None = None):
    """
    Возвращает (embeddings_service, retrieval_service).
    Пересоздаёт сервисы при смене base_url или модели embeddings.
    llm_client используется для multi-query и re-ranking.
    """
    global _rag_config_key, _rag_embeddings_service, _rag_retrieval_service

    base_url = OLLAMA_BASE_URL
    embeddings_model = OLLAMA_EMBEDDINGS_MODEL
    if ollama_config:
        base_url = ollama_config.get("base_url", base_url)
        embeddings_model = ollama_config.get("embeddings_model", embeddings_model)

    key = (base_url, embeddings_model)
    if _rag_embeddings_service is None or _rag_config_key != key:
        _rag_config_key = key
        _rag_embeddings_service = OllamaEmbeddingsService(
            base_url=base_url,
            model=embeddings_model,
            request_timeout=AI_ASSISTANT_REQUEST_TIMEOUT,
        )
        _rag_retrieval_service = HybridRAGRetrievalService(
            embeddings_service=_rag_embeddings_service,
            top_k=RAG_TOP_K,
            similarity_threshold=RAG_SIMILARITY_THRESHOLD,
            rerank_top_n=RAG_RERANK_TOP_N,
            reranking_enabled=RERANKING_ENABLED,
            multi_query_enabled=MULTI_QUERY_ENABLED,
            llm_client=llm_client,
        )
    elif llm_client is not None and _rag_retrieval_service is not None:
        # Обновляем llm_client если передан
        _rag_retrieval_service.llm_client = llm_client

    return _rag_embeddings_service, _rag_retrieval_service


def get_rag_context(
    query: str,
    user,
    ollama_config: dict[str, Any] | None = None,
    enabled: bool | None = None,
    document_ids: list[str] | None = None,
) -> tuple[str, list]:
    if enabled is None:
        enabled = RAG_ENABLED
    if not enabled:
        return "", []

    try:
        _, retrieval_service = get_rag_services(ollama_config)
        context, chunks = retrieval_service.retrieve_and_build_context(
            query=query,
            user=user,
            max_context_length=RAG_MAX_CONTEXT_LENGTH,
            document_ids=document_ids,
        )
        return context, chunks
    except RAGRetrievalError as e:
        logger.warning("Ошибка RAG retrieval: %s", e)
        return "", []
    except Exception as e:
        logger.error("Неожиданная ошибка RAG retrieval: %s", e, exc_info=True)
        return "", []
