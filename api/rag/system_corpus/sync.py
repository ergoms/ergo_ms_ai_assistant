"""
Синхронизация пользовательского корпуса функционала системы в KnowledgeDocument + embeddings.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.utils.huggingface_snapshot import is_huggingface_repo_id

from ...models import KnowledgeDocument
from ...settings import (
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_SYSTEM_CORPUS_ENABLED,
    RAG_SYSTEM_CORPUS_MAX_FILE_BYTES,
)
from ...indexing_queue import enqueue_knowledge_document_index
from ..indexing import RAGIndexingError, RAGIndexingService
from .sources import iter_system_corpus_documents, project_root

logger = logging.getLogger(__name__)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sync_system_corpus(
    *,
    embeddings_service,
    force: bool = False,
    dry_run: bool = False,
    root: Optional[Path] = None,
    use_celery: bool = True,
) -> Dict[str, Any]:
    """
    Upsert документов корпуса (меню, модули, UI-строки, guides) и индексация.

    Returns:
        Сводка: created, updated, skipped, removed, errors, indexed
    """
    if not RAG_SYSTEM_CORPUS_ENABLED and not force:
        return {
            'success': False,
            'error': 'RAG_SYSTEM_CORPUS_ENABLED=false',
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'removed': 0,
            'indexed': 0,
            'errors': [],
        }

    root = (root or project_root()).resolve()

    # Fail-fast: не гонять весь корпус, если embeddings недоступны
    try:
        health = embeddings_service.check_health()
        if not health.get('available'):
            return {
                'success': False,
                'error': (
                    'Ollama недоступен. Запустите: ergoms ollama_framework:start-ollama'
                ),
                'created': 0,
                'updated': 0,
                'skipped': 0,
                'removed': 0,
                'indexed': 0,
                'errors': [],
            }
        if health.get('model_available') is False:
            model = health.get('model') or 'embeddinggemma'
            if is_huggingface_repo_id(model):
                hint = (
                    f'OLLAMA_EMBEDDINGS_MODEL «{model}» — снимок Hugging Face, '
                    f'не модель Ollama. Укажите имя из библиотеки Ollama '
                    f'(например embeddinggemma) или: '
                    f'ergoms ollama_framework:pull-setup-models'
                )
            else:
                hint = (
                    f'Модель embeddings «{model}» не найдена. '
                    f'Установите: ergoms ollama_framework:ollama --pull {model}'
                )
            return {
                'success': False,
                'error': hint,
                'created': 0,
                'updated': 0,
                'skipped': 0,
                'removed': 0,
                'indexed': 0,
                'errors': [],
            }
    except Exception as exc:
        return {
            'success': False,
            'error': f'Embeddings недоступны: {exc}',
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'removed': 0,
            'indexed': 0,
            'errors': [],
        }

    indexing_service = RAGIndexingService(
        embeddings_service=embeddings_service,
        chunk_size=RAG_CHUNK_SIZE,
        chunk_overlap=RAG_CHUNK_OVERLAP,
    )

    stats = {
        'success': True,
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'removed': 0,
        'indexed': 0,
        'queued': 0,
        'errors': [],
        'files': 0,
    }

    seen_sources: set[str] = set()

    for source_id, title, content in iter_system_corpus_documents(
        root=root,
        max_file_bytes=RAG_SYSTEM_CORPUS_MAX_FILE_BYTES,
    ):
        stats['files'] += 1
        seen_sources.add(source_id)
        try:
            text = content.strip()
            if not text:
                stats['skipped'] += 1
                continue

            digest = _content_hash(text)
            existing = KnowledgeDocument.objects.filter(
                corpus=KnowledgeDocument.CORPUS_SYSTEM,
                source=source_id,
            ).first()

            if existing:
                meta = existing.metadata or {}
                if not force and meta.get('content_hash') == digest and existing.is_indexed:
                    stats['skipped'] += 1
                    continue
                if dry_run:
                    stats['updated'] += 1
                    continue
                existing.title = title
                existing.content = text
                existing.user = None
                existing.file_type = 'md'
                existing.metadata = {
                    **meta,
                    'content_hash': digest,
                    'rel_path': source_id,
                    'system_corpus': True,
                    'audience': 'end_user',
                }
                existing.is_indexed = False
                existing.indexed_at = None
                existing.save()
                document = existing
                stats['updated'] += 1
            else:
                if dry_run:
                    stats['created'] += 1
                    continue
                document = KnowledgeDocument.objects.create(
                    user=None,
                    corpus=KnowledgeDocument.CORPUS_SYSTEM,
                    title=title,
                    content=text,
                    source=source_id,
                    file_type='md',
                    metadata={
                        'content_hash': digest,
                        'rel_path': source_id,
                        'system_corpus': True,
                        'audience': 'end_user',
                    },
                )
                stats['created'] += 1

            if dry_run:
                continue

            if use_celery:
                enqueue_knowledge_document_index(document, force=True)
                stats['queued'] += 1
                continue

            result = indexing_service.index_document(document, force_reindex=True)
            if result.get('success'):
                stats['indexed'] += 1
            else:
                err = result.get('error') or 'indexing failed'
                stats['errors'].append({'source': source_id, 'error': err})
                logger.warning('Не удалось проиндексировать %s: %s', source_id, err)

        except RAGIndexingError as exc:
            stats['errors'].append({'source': source_id, 'error': str(exc)})
            logger.warning('Ошибка индексации %s: %s', source_id, exc)
        except Exception as exc:
            stats['errors'].append({'source': source_id, 'error': str(exc)})
            logger.error('Ошибка sync корпуса %s: %s', source_id, exc, exc_info=True)

    # Удаляем устаревшие системные документы (в т.ч. старый developer-корпус)
    stale_qs = KnowledgeDocument.objects.filter(
        corpus=KnowledgeDocument.CORPUS_SYSTEM,
    ).exclude(source__in=seen_sources)
    stale_count = stale_qs.count()
    if stale_count and not dry_run:
        stale_qs.delete()
    stats['removed'] = stale_count

    if stats['errors']:
        stats['success'] = False

    return stats
