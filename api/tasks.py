"""Фоновые задачи ai_assistant: индексация RAG."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='modules.ai_assistant.api.tasks.index_knowledge_document')
def index_knowledge_document(document_id: str, force: bool = False) -> dict:
    from .models import KnowledgeDocument
    from .rag import RAGIndexingError, RAGIndexingService
    from .settings import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE
    from .views.helpers import _get_rag_services

    try:
        document = KnowledgeDocument.objects.get(id=document_id)
    except KnowledgeDocument.DoesNotExist:
        logger.warning('Документ %s не найден для индексации', document_id)
        return {'success': False, 'error': 'document not found'}

    document.indexing_status = KnowledgeDocument.INDEXING_STATUS_RUNNING
    document.indexing_error = ''
    document.save(update_fields=['indexing_status', 'indexing_error'])

    try:
        embeddings_service, _ = _get_rag_services()
        indexing_service = RAGIndexingService(
            embeddings_service=embeddings_service,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )
        if force:
            result = indexing_service.reindex_document(document)
        else:
            result = indexing_service.index_document(document)

        document.refresh_from_db()
        if result.get('success'):
            document.indexing_status = KnowledgeDocument.INDEXING_STATUS_DONE
            document.indexing_error = ''
        else:
            document.indexing_status = KnowledgeDocument.INDEXING_STATUS_FAILED
            document.indexing_error = result.get('error') or result.get('message') or 'indexing failed'
        document.save(update_fields=['indexing_status', 'indexing_error'])
        return result
    except RAGIndexingError as exc:
        document.indexing_status = KnowledgeDocument.INDEXING_STATUS_FAILED
        document.indexing_error = str(exc)
        document.save(update_fields=['indexing_status', 'indexing_error'])
        logger.error('Ошибка индексации документа %s: %s', document_id, exc)
        raise
    except Exception as exc:
        document.indexing_status = KnowledgeDocument.INDEXING_STATUS_FAILED
        document.indexing_error = str(exc)
        document.save(update_fields=['indexing_status', 'indexing_error'])
        logger.error('Неожиданная ошибка индексации %s: %s', document_id, exc, exc_info=True)
        raise
