"""Контракт хранения файлов ai_assistant через media_api."""

from __future__ import annotations

import os
from pathlib import Path

from src.core.utils.media_client import get_media_client, get_scratch_store
from src.core.utils.media_signing import get_signed_media_url, get_signed_media_url_from_field

MODULE_PREFIX = 'ai_assistant'


def media_relative_path(*parts: str) -> str:
    return '/'.join([MODULE_PREFIX, *[p.strip('/') for p in parts if p]])


def commit_local_file(local_path: str, target: str) -> str:
    return get_media_client().commit_local(local_path, target)


def signed_url(path: str) -> str | None:
    if not path:
        return None
    return get_signed_media_url(path)


def signed_url_from_field(file_field) -> str | None:
    return get_signed_media_url_from_field(file_field)


def scratch_session(name: str):
    return get_scratch_store().session(name)


def localize_path(stored_path: str):
    """Локализует файл из media_api; caller должен вызвать .release()."""
    return get_media_client().localize(stored_path)


def parse_localized_document(stored_path: str, filename: str | None = None):
    """Парсит документ из media_api через localize."""
    from .rag.parser import DocumentParserService

    localized = localize_path(stored_path)
    try:
        return DocumentParserService.parse_document(
            file_path=localized.path,
            filename=filename or os.path.basename(stored_path),
        )
    finally:
        localized.release()


def commit_generated_document(local_path: Path | str, user_id: int | None, filename: str) -> str:
    """Коммитит сгенерированный документ в media_api."""
    user_part = f'user_{user_id}' if user_id else 'anonymous'
    target = media_relative_path('generated', user_part, filename)
    return commit_local_file(str(local_path), target)
