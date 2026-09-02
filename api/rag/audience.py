"""Метка audience системного корпуса RAG: user | admin."""
from __future__ import annotations

from pathlib import Path

AUDIENCE_USER = 'user'
AUDIENCE_ADMIN = 'admin'

ADMIN_GUIDE_STEMS = frozenset({
    'admin_panel_overview',
    'users_roles_access',
})

ADMIN_SOURCE_IDS = frozenset({
    'user_ui/site_menu.md',
    'user_ui/installed_modules.md',
})


def normalize_audience(value: str | None) -> str:
    raw = (value or '').strip().lower()
    if raw in ('admin', 'administrator'):
        return AUDIENCE_ADMIN
    return AUDIENCE_USER


def audience_for_source(source_id: str, *, pack_audience: str | None = None) -> str:
    """audience документа корпуса по источнику или метке пакета."""
    if pack_audience:
        return normalize_audience(pack_audience)
    source = (source_id or '').replace('\\', '/')
    if source in ADMIN_SOURCE_IDS:
        return AUDIENCE_ADMIN
    if source.startswith('user_guides/core/'):
        stem = Path(source).stem
        if stem in ADMIN_GUIDE_STEMS:
            return AUDIENCE_ADMIN
    if source.startswith('knowledge/core/'):
        doc_id = source.rsplit('/', 1)[-1]
        stem = doc_id.split(':', 1)[-1]
        if stem in ADMIN_GUIDE_STEMS:
            return AUDIENCE_ADMIN
    return AUDIENCE_USER


def is_admin_audience(value: str | None) -> bool:
    return normalize_audience(value) == AUDIENCE_ADMIN
