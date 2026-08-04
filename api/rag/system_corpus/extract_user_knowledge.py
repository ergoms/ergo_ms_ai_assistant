"""
Сбор пользовательских знаний о функционале сайта для RAG.

Источники: меню, каталог модулей/прав, подписи UI (i18n), локальные guides.
Не индексирует .docs, .cursor/rules и developer README.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from src.config.paths import SYSTEM_DIR

logger = logging.getLogger(__name__)

DocumentTuple = Tuple[str, str, str]  # source_id, title, content

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
    # Технические идентификаторы без пробелов и кириллицы
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
    # Грубый срез комментариев
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    raw = re.sub(r'//.*?$', '', raw, flags=re.MULTILINE)

    values: List[str] = []
    seen: set[str] = set()
    for match in _STRING_VALUE_RE.finditer(raw):
        value = _unescape_js_string(match.group(1) if match.group(1) is not None else match.group(2))
        if not _is_useful_ui_string(value):
            continue
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _iter_locale_files(root: Path) -> Iterator[Path]:
    patterns = [
        'core/client/src/i18n/locales/ru/**/*.js',
        'modules/*/client/js/locales/ru.js',
        'modules/*/client/js/locales.js',
        'modules/*/client/js/locales/ru/*.js',
    ]
    seen: set[str] = set()
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix().lower()
            if any(part in rel for part in _SKIP_LOCALE_PARTS):
                continue
            # Для locales.js модулей берём только если внутри есть ru-блок / кириллица
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            yield path


def build_locale_documents(root: Path | None = None) -> List[DocumentTuple]:
    root = (root or Path(SYSTEM_DIR)).resolve()
    docs: List[DocumentTuple] = []
    for path in _iter_locale_files(root):
        values = _extract_strings_from_js(path)
        if not values:
            continue
        rel = path.relative_to(root).as_posix()
        # Фильтр: для en-only файлов без кириллицы пропускаем, если это не core ru
        has_cyrillic = any(re.search(r'[А-Яа-яЁё]', v) for v in values)
        if not has_cyrillic and '/locales/ru' not in rel.replace('\\', '/'):
            # modules/*/locales.js часто содержит ru/en/fr — оставляем, если есть кириллица
            continue
        lines = [
            f'# Подписи интерфейса: {rel}',
            '',
            'Тексты экранов, кнопок и подсказок сайта (для ответов пользователю).',
            '',
        ]
        for value in values:
            lines.append(f'- {value}')
        docs.append((
            f'user_ui/{rel}',
            f'Интерфейс: {path.stem}',
            '\n'.join(lines),
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
        '# Разделы сайта (боковое меню)',
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
    return (
        'user_ui/site_menu.md',
        'Разделы сайта (меню)',
        '\n'.join(lines),
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
        '# Возможности и модули сайта',
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
        perms = mod.get('permissions') or {}
        if perms:
            lines.append('Доступные действия (права):')
            for key, perm_label in sorted(perms.items(), key=lambda x: str(x[1] or x[0])):
                human = (perm_label or key).strip()
                lines.append(f'- {human}')
        else:
            lines.append('Модуль установлен; подробные права в каталоге не описаны.')
        lines.append('')

    return (
        'user_ui/installed_modules.md',
        'Модули и возможности сайта',
        '\n'.join(lines),
    )


def build_guide_documents(root: Path | None = None) -> List[DocumentTuple]:
    """Локальные пользовательские шпаргалки модуля ai_assistant."""
    guides_dir = Path(__file__).resolve().parent / 'guides'
    if not guides_dir.is_dir():
        return []
    docs: List[DocumentTuple] = []
    for path in sorted(guides_dir.glob('*.md')):
        try:
            content = path.read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if not content:
            continue
        source = f'user_guides/{path.name}'
        title = f'Справка: {path.stem.replace("_", " ")}'
        # Первая строка # заголовка как title
        first = content.splitlines()[0].strip()
        if first.startswith('# '):
            title = first[2:].strip()
        docs.append((source, title, content))
    return docs


def iter_user_knowledge_documents(root: Path | None = None) -> Iterator[DocumentTuple]:
    """Все документы пользовательского корпуса (source, title, content)."""
    root = (root or Path(SYSTEM_DIR)).resolve()
    seen: set[str] = set()

    for builder in (build_menu_document, build_modules_document):
        doc = builder()
        if not doc:
            continue
        source, title, content = doc
        if source in seen or not content.strip():
            continue
        seen.add(source)
        yield source, title, content

    for source, title, content in build_guide_documents(root):
        if source in seen or not content.strip():
            continue
        seen.add(source)
        yield source, title, content

    for source, title, content in build_locale_documents(root):
        if source in seen or not content.strip():
            continue
        seen.add(source)
        yield source, title, content
