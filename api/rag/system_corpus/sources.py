"""
Источники системного корпуса: пользовательский функционал сайта.

Developer-документация (.docs, .cursor/rules, AGENTS.md) не индексируется.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Tuple

from src.config.paths import SYSTEM_DIR

from .extract_user_knowledge import iter_user_knowledge_documents

DocumentTuple = Tuple[str, str, str]  # source, title, content


def project_root() -> Path:
    return Path(SYSTEM_DIR).resolve()


def iter_system_corpus_documents(
    *,
    root: Path | None = None,
    max_file_bytes: int | None = None,
) -> Iterator[DocumentTuple]:
    """
    Yields (source_id, title, content) для пользовательского корпуса.

    max_file_bytes ограничивает размер content (символы ≈ байты для UTF-8 текста).
    """
    for source, title, content in iter_user_knowledge_documents(root=root):
        text = (content or '').strip()
        if not text:
            continue
        if max_file_bytes is not None and len(text.encode('utf-8')) > max_file_bytes:
            text = text.encode('utf-8')[:max_file_bytes].decode('utf-8', errors='ignore')
            text = text.rstrip() + '\n…'
        yield source, title, text


def iter_system_corpus_files(
    *,
    root: Path | None = None,
    max_file_bytes: int | None = None,
):
    """Обратная совместимость: не используется файловый обход developer-доков."""
    del root, max_file_bytes
    return iter(())


def title_for_source(rel_path: str) -> str:
    return f'Справка ERGO MS: {rel_path}'
