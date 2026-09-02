"""
Сбор пользовательского корпуса для RAG.

Пакеты knowledge/ — через механизм ядра. Меню, каталог модулей и строки
интерфейса собирает этот модуль из API ядра, без обхода чужого кода.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from src.config.paths import SYSTEM_DIR

from ..audience import audience_for_source

logger = logging.getLogger(__name__)

DocumentTuple = Tuple[str, str, str, str]  # source_id, title, content, audience

_STRING_VALUE_RE = re.compile(
    r""":\s*(?:'((?:\\.|[^'\\])*)'|"((?:\\.|[^"\\])*)")""",
)
_SKIP_LOCALE_PARTS = (
    'module_template',
    'node_modules',
    '__pycache__',
    '.git/',
)
_SKIP_VALUE_PREFIXES = ('http://', 'https://', 'data:', '#')


def _unescape_js_string(value: str) -> str:
    return (
        value.replace("\\'", "'")
        .replace('\\"', '"')
        .replace('\\n', '\n')
        .replace('\\\\', '\\')
    )


def _is_useful_ui_string(value: str) -> bool:
    text = value.strip()
    if len(text) < 4:
        return False
    if any(text.startswith(p) for p in _SKIP_VALUE_PREFIXES):
        return False
    if re.fullmatch(r'#[0-9a-fA-F]{3,8}', text):
        return False
    if not re.search(r'[A-Za-zА-Яа-яЁё]', text):
        return False
    if ' ' not in text and not re.search(r'[А-Яа-яЁё]', text) and len(text) < 40:
        if re.fullmatch(r'[A-Za-z0-9_.:-]+', text):
            return False
    return True


def _extract_strings_from_js(path: Path) -> List[str]:
    try:
        raw = path.read_text(encoding='utf-8')
    except OSError as exc:
        logger.warning('Не удалось прочитать %s: %s', path, exc)
        return []
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    raw = re.sub(r'//.*?$', '', raw, flags=re.MULTILINE)

    values: List[str] = []
    seen: set[str] = set()
    for match in _STRING_VALUE_RE.finditer(raw):
        value = _unescape_js_string(match.group(1) if match.group(1) is not None else match.group(2))
        if not _is_useful_ui_string(value) or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _iter_locale_files(root: Path, language: str = 'ru') -> Iterator[Path]:
    """Ядро и установленные модули, без зашитых имён в коде."""
    seen: set[str] = set()
    lang = (language or 'ru').strip() or 'ru'

    def _yield(path: Path) -> Iterator[Path]:
        if not path.is_file():
            return
        rel = path.relative_to(root).as_posix().lower()
        if any(part in rel for part in _SKIP_LOCALE_PARTS):
            return
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        yield path

    core_dir = root / 'core' / 'client' / 'src' / 'i18n' / 'locales' / lang
    if core_dir.is_dir():
        for path in sorted(core_dir.rglob('*.js')):
            yield from _yield(path)

    from src.core.utils.module_registry import get_installed_module_names

    for name in get_installed_module_names():
        client = root / 'modules' / name / 'client'
        if not client.is_dir():
            continue
        for path in (
            client / 'js' / 'locales.js',
            client / 'js' / f'locales/{lang}.js',
        ):
            yield from _yield(path)
        lang_dir = client / 'js' / 'locales' / lang
        if lang_dir.is_dir():
            for path in sorted(lang_dir.rglob('*.js')):
                yield from _yield(path)
        for path in sorted(client.glob('*/js/locales.js')):
            yield from _yield(path)
        for path in sorted(client.glob(f'*/js/locales/{lang}.js')):
            yield from _yield(path)
        for path in sorted(client.glob(f'*/js/locales/{lang}/*.js')):
            yield from _yield(path)


def build_locale_documents(root: Path | None = None) -> List[DocumentTuple]:
    root = (root or Path(SYSTEM_DIR)).resolve()
    docs: List[DocumentTuple] = []
    for path in _iter_locale_files(root):
        values = _extract_strings_from_js(path)
        if not values:
            continue
        rel = path.relative_to(root).as_posix()
        has_cyrillic = any(re.search(r'[А-Яа-яЁё]', v) for v in values)
        if not has_cyrillic and '/locales/ru' not in rel.replace('\\', '/'):
            continue
        lines = [
            f'# Подписи интерфейса: {rel}',
            '',
            'Тексты экранов, кнопок и подсказок системы (для ответов пользователю).',
            '',
        ]
        lines.extend(f'- {value}' for value in values)
        source = f'user_ui/{rel}'
        docs.append((
            source,
            f'Интерфейс: {path.stem}',
            '\n'.join(lines),
            audience_for_source(source),
        ))
    return docs


def build_menu_document() -> DocumentTuple | None:
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
            lines.append('Модуль установлен; подробные права в каталоге не описаны.')
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
            title,
            text,
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
    """Корпус модуля: меню, каталог, пакеты ядра, строки интерфейса."""
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

    for source, title, content, audience in build_locale_documents(root):
        if source in seen or not content.strip():
            continue
        seen.add(source)
        yield source, title, content, audience
