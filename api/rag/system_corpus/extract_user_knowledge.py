"""
Сбор пользовательского корпуса для RAG.

Пакеты knowledge/ — через механизм ядра. Меню и каталог модулей —
из API ядра. Каталог экранов приходит уже внутри пакетов, без обхода
локалей и Vue на диске процесса ассистента.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from src.config.paths import SYSTEM_DIR
from src.core.utils.user_facing import prepare_user_facing_text
from src.core.utils.knowledge_pack import html_to_plain

from ..audience import audience_for_source

logger = logging.getLogger(__name__)

DocumentTuple = Tuple[str, str, str, str]  # source_id, title, content, audience

_capabilities_cache = None


def _capabilities_from_core():
    global _capabilities_cache
    if _capabilities_cache is not None:
        return _capabilities_cache
    try:
        from src.core.integrations import bridge
        from src.core.integrations.module_contracts import CORE_KNOWLEDGE_USER_CAPABILITIES
        op_name = CORE_KNOWLEDGE_USER_CAPABILITIES
    except ImportError:
        from src.core.integrations import bridge
        op_name = 'core.knowledge.user_capabilities'
    try:
        result = bridge.call(op_name, full=True, default=None)
    except Exception as exc:
        logger.warning('Каталог разделов с ядра недоступен: %s', exc)
        _capabilities_cache = {}
        return _capabilities_cache
    _capabilities_cache = result if isinstance(result, dict) else {}
    return _capabilities_cache


def build_menu_document() -> DocumentTuple | None:
    payload = _capabilities_from_core()
    remote_lines = list((payload or {}).get('menu_lines') or [])
    if remote_lines:
        source = 'user_ui/site_menu.md'
        return (
            source,
            'Разделы системы (меню)',
            '\n'.join([
                '# Разделы системы (боковое меню)',
                '',
                'Карта разделов, доступных пользователям в интерфейсе ERGO MS.',
                'Помоги найти, куда нажать, чтобы открыть нужную функцию.',
                '',
                *remote_lines,
            ]),
            audience_for_source(source),
        )
    try:
        from src.core.cms.adp.menu.models import MenuItem
    except Exception as exc:
        logger.warning('Меню недоступно для корпуса: %s', exc)
        return None

    items = (
        MenuItem.objects.filter(is_active=True)
        .order_by('order', 'name')
        .only('name', 'route_name', 'item_type', 'is_admin_only', 'parent_id', 'module_source')
    )
    if not items.exists():
        return None

    by_parent: Dict[int | None, list] = {}
    for item in items:
        by_parent.setdefault(item.parent_id, []).append(item)

    lines = [
        '# Разделы системы (боковое меню)',
        '',
        'Карта разделов, доступных пользователям в интерфейсе ERGO MS.',
        'Помоги найти, куда нажать, чтобы открыть нужную функцию.',
        '',
    ]

    def walk(parent_id, depth: int) -> None:
        for item in by_parent.get(parent_id, []):
            indent = '  ' * depth
            admin = ' (только администратор)' if item.is_admin_only else ''
            route = f', раздел «{item.route_name}»' if item.route_name else ''
            lines.append(f'{indent}- **{item.name}**{admin}{route}')
            walk(item.id, depth + 1)

    walk(None, 0)
    source = 'user_ui/site_menu.md'
    return (
        source,
        'Разделы системы (меню)',
        '\n'.join(lines),
        audience_for_source(source),
    )


def build_modules_document() -> DocumentTuple | None:
    payload = _capabilities_from_core()
    remote_modules = list((payload or {}).get('modules') or [])
    if remote_modules:
        lines = [
            '# Возможности и модули системы',
            '',
            'Установленные модули ERGO MS и связанные с ними действия (с точки зрения пользователя).',
            'Объясняй, что можно сделать в системе, без технических деталей разработки.',
            '',
        ]
        for item in remote_modules:
            if not isinstance(item, dict):
                continue
            label = (item.get('label') or item.get('name') or '').strip()
            if not label:
                continue
            lines.append(f'## {label}')
            lines.append('')
            description = (item.get('user_description') or '').strip()
            lines.append(description or 'Подробности — в пунктах бокового меню этого раздела.')
            lines.append('')
        source = 'user_ui/installed_modules.md'
        return (
            source,
            'Модули и возможности системы',
            '\n'.join(lines),
            audience_for_source(source),
        )
    try:
        from src.core.cms.adp.services.permission_catalog import get_modules_catalog
    except Exception as exc:
        logger.warning('Каталог модулей недоступен: %s', exc)
        return None

    modules = get_modules_catalog(include_disabled=False)
    if not modules:
        return None

    lines = [
        '# Возможности и модули системы',
        '',
        'Установленные модули ERGO MS и связанные с ними действия (с точки зрения пользователя).',
        'Объясняй, что можно сделать в системе, без технических деталей разработки.',
        '',
    ]
    for mod in modules:
        if mod.get('disabled'):
            continue
        label = mod.get('module_label') or mod.get('module_name')
        lines.append(f'## {label}')
        lines.append('')
        description = (mod.get('user_description') or '').strip()
        if description:
            lines.append(description)
            lines.append('')
        perms = mod.get('permissions') or {}
        if perms:
            lines.append('Доступные действия (права):')
            for key, perm_label in sorted(perms.items(), key=lambda x: str(x[1] or x[0])):
                human = (perm_label or key).strip()
                lines.append(f'- {human}')
        elif not description:
            lines.append('Подробности — в пунктах бокового меню этого раздела.')
        lines.append('')

    source = 'user_ui/installed_modules.md'
    return (
        source,
        'Модули и возможности системы',
        '\n'.join(lines),
        audience_for_source(source),
    )


@dataclass
class PackLoadState:
    """Результат чтения пакетов knowledge/: для prune при недоступном соседе."""

    complete: bool = True
    failed_owners: frozenset[str] = field(default_factory=frozenset)
    sources: List[DocumentTuple] = field(default_factory=list)


_pack_state = PackLoadState()


def pack_sync_state() -> PackLoadState:
    return _pack_state


def load_pack_documents_for_sync() -> PackLoadState:
    """Забирает опубликованные пакеты через механизм ядра."""
    global _pack_state
    try:
        from src.core.utils.knowledge_pack import load_published_pack_documents

        result = load_published_pack_documents()
    except Exception as exc:
        logger.warning('Пакеты справки недоступны: %s', exc)
        _pack_state = PackLoadState(complete=False)
        return _pack_state

    docs: List[DocumentTuple] = []
    for item in result.get('documents') or []:
        text = str(item.get('text') or '').strip()
        if not text:
            continue
        source = str(item.get('source') or '').strip()
        if not source:
            owner = str(item.get('owner') or '').strip()
            doc_id = str(item.get('id') or '').strip()
            if not owner or not doc_id:
                continue
            source = f'knowledge/{owner}/{doc_id}'
        title = str(item.get('title') or source)
        docs.append((
            source,
            prepare_user_facing_text(html_to_plain(title)),
            prepare_user_facing_text(html_to_plain(text)),
            audience_for_source(source, pack_audience=item.get('audience')),
        ))

    failed = result.get('failed_owners')
    if failed is None:
        logger.warning('Дескрипторы пакетов справки недоступны, старый индекс сохранён')
        _pack_state = PackLoadState(complete=False, sources=docs)
    else:
        _pack_state = PackLoadState(
            complete=True,
            failed_owners=frozenset(str(name) for name in failed),
            sources=docs,
        )
        if failed:
            logger.warning(
                'Часть пакетов справки недоступна, старый индекс сохранён: %s',
                ', '.join(sorted(str(name) for name in failed)),
            )
    return _pack_state


def build_published_pack_documents(root: Path | None = None) -> List[DocumentTuple]:
    del root
    return list(load_pack_documents_for_sync().sources)


def iter_user_knowledge_documents(root: Path | None = None) -> Iterator[DocumentTuple]:
    """Корпус модуля: меню, каталог модулей и пакеты knowledge/ (включая ui_catalog)."""
    root = (root or Path(SYSTEM_DIR)).resolve()
    seen: set[str] = set()

    for builder in (build_menu_document, build_modules_document):
        doc = builder()
        if not doc:
            continue
        source, title, content, audience = doc
        if source in seen or not content.strip():
            continue
        seen.add(source)
        yield source, title, content, audience

    for source, title, content, audience in build_published_pack_documents(root):
        if source in seen or not content.strip():
            continue
        seen.add(source)
        yield source, title, content, audience
