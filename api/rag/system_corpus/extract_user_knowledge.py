"""
Пользовательский корпус для RAG: ядро собирает, модуль только размечает audience.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Tuple

from src.core.utils.help_corpus import collect_help_corpus, help_corpus_sync_state

from ..audience import audience_for_source

DocumentTuple = Tuple[str, str, str, str]  # source_id, title, content, audience


@dataclass
class PackLoadState:
    """Результат чтения пакетов knowledge/: для prune при недоступном соседе."""

    complete: bool = True
    failed_owners: frozenset[str] = field(default_factory=frozenset)
    sources: List[DocumentTuple] = field(default_factory=list)


def pack_sync_state() -> PackLoadState:
    state = help_corpus_sync_state()
    return PackLoadState(
        complete=state.complete,
        failed_owners=state.failed_owners,
    )


def iter_user_knowledge_documents(root: Path | None = None) -> Iterator[DocumentTuple]:
    """Документы корпуса платформы (source, title, content, audience)."""
    result = collect_help_corpus(root)
    for item in result.get('documents') or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get('text') or '').strip()
        source = str(item.get('source') or '').strip()
        if not text or not source:
            continue
        title = str(item.get('title') or source)
        yield (
            source,
            title,
            text,
            audience_for_source(source, pack_audience=item.get('audience')),
        )
