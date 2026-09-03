"""Проверка, что названные кнопки и поля есть в контексте справки."""
from __future__ import annotations

import re
from typing import Iterable

REASON_UNGROUNDED_UI = 'ungrounded_ui'

_CLAIM_PATTERNS = (
    re.compile(r'кнопк[ауиеё]\s+[«"]([^»"]{2,80})[»"]', re.I),
    re.compile(r'поле\s+[«"]([^»"]{2,80})[»"]', re.I),
    re.compile(r'раздел\s+[«"]([^»"]{2,80})[»"]', re.I),
    re.compile(r'нажмите\s+[«"]([^»"]{2,80})[»"]', re.I),
    re.compile(r'кнопк[ауиеё]\s+[«"]?([А-Яа-яЁёA-Za-z][^.,;:\n]{1,60})', re.I),
    re.compile(r'поле\s+[«"]?([А-Яа-яЁёA-Za-z][^.,;:\n]{1,60})', re.I),
    re.compile(r'[«"]([^»"]{3,80})[»"]'),
)

_GENERIC = frozenset({
    'меню',
    'настройки',
    'система',
    'раздел',
    'кнопка',
    'поле',
    'форма',
    'профиль',
    'администратор',
    'пользователь',
    'справка',
    'меню пользователя',
    'боковое меню',
})

_REFUSAL = {
    'ru': (
        'В доступной справке нет такого раздела, кнопки или поля. '
        'Не могу подсказать точнее, чтобы не выдумать название.'
    ),
    'en': (
        'The available help does not mention that section, button, or field. '
        'I will not invent a label.'
    ),
    'fr': (
        'L’aide disponible ne mentionne pas cette section, ce bouton ou ce champ. '
        'Je ne vais pas inventer un libellé.'
    ),
}


def grounding_refusal_text(ui_language: str) -> str:
    key = (ui_language or 'ru').strip().lower().split('-', 1)[0]
    return _REFUSAL.get(key) or _REFUSAL['ru']


def _normalize_label(value: str) -> str:
    text = re.sub(r'\s+', ' ', (value or '')).strip().strip('«»"\'.,;:')
    return text.casefold()


def extract_ui_claims(answer: str) -> list[str]:
    claims: list[str] = []
    seen: set[str] = set()
    blob = answer or ''
    for pattern in _CLAIM_PATTERNS:
        for match in pattern.finditer(blob):
            raw = (match.group(1) or '').strip()
            raw = raw.split(' и ')[0].strip()
            key = _normalize_label(raw)
            if len(key) < 3 or key in _GENERIC or key in seen:
                continue
            seen.add(key)
            claims.append(raw)
    return claims


def ungrounded_ui_claims(answer: str, context: str) -> list[str]:
    hay = _normalize_label(context)
    if not hay:
        return extract_ui_claims(answer)
    missing: list[str] = []
    for claim in extract_ui_claims(answer):
        needle = _normalize_label(claim)
        if needle and needle not in hay:
            missing.append(claim)
    return missing


def knowledge_text_from_messages(messages: Iterable[dict] | None) -> str:
    parts: list[str] = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get('content') or '')
        role = item.get('role')
        if role == 'system' or '[ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]' in content:
            parts.append(content)
        elif '[ВОЗМОЖНОСТИ СИСТЕМЫ]' in content:
            parts.append(content)
    return '\n'.join(parts)


def filter_ungrounded_ui(
    answer: str,
    *,
    knowledge_context: str,
    ui_language: str = 'ru',
) -> tuple[str, bool]:
    """Если ответ называет кнопку/поле вне контекста — заменить на отказ."""
    if not (answer or '').strip() or not (knowledge_context or '').strip():
        return answer, False
    missing = ungrounded_ui_claims(answer, knowledge_context)
    if not missing:
        return answer, False
    return grounding_refusal_text(ui_language), True
