"""Celery-очередь индексации документов RAG."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models import KnowledgeDocument

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


class IndexingQueueError(RuntimeError):
    """Не удалось поставить задачу индексации в Celery."""


def enqueue_knowledge_document_index(
    document: KnowledgeDocument,
    *,
    force: bool = False,
) -> None:
    """Ставит документ в очередь фоновой индексации."""
    from ..tasks import index_knowledge_document

    document.indexing_status = KnowledgeDocument.INDEXING_STATUS_PENDING
    document.indexing_error = ''
    document.save(update_fields=['indexing_status', 'indexing_error'])

    try:
        index_knowledge_document.delay(str(document.id), force=force)
    except Exception as exc:
        document.indexing_status = KnowledgeDocument.INDEXING_STATUS_FAILED
        document.indexing_error = str(exc)
        document.save(update_fields=['indexing_status', 'indexing_error'])
        raise IndexingQueueError(
            'Не удалось поставить индексацию в очередь Celery. Запустите: ergoms start-worker'
        ) from exc
