"""
Правила защиты чата: jailbreak и админ-howto на входе, утечки на выходе.

Без второго вызова LLM. Глобальный админ проверку не проходит.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from ..assistant_role import assistant_is_admin
from ..models import ChatMessage
from .grounding import filter_ungrounded_ui

REASON_JAILBREAK = 'jailbreak'
REASON_ADMIN_HOWTO = 'admin_howto'
REASON_OUTPUT_LEAK = 'output_leak'

_HISTORY_USER_LIMIT = 8

_JAILBREAK_PATTERNS = (
    re.compile(r'ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|prompts?)', re.I),
    re.compile(r'забудь\s+(все\s+)?(предыдущие\s+)?(инструкции|правила|указания)', re.I),
    re.compile(r'(you\s+are\s+now|act\s+as|pretend\s+(you\s+are|to\s+be))\s+(an?\s+)?(admin|administrator)', re.I),
    re.compile(r'(ты\s+теперь|притворись|сыграй\s+роль)\s+(админ\w*|администратор\w*)', re.I),
    re.compile(r'(show|reveal|print)\s+(me\s+)?(the\s+)?(system\s+)?(prompt|instructions?)', re.I),
    re.compile(r'покажи\s+(системн\w*\s+)?(промпт|подсказк\w*|инструкц\w*)', re.I),
    re.compile(r'\b(jailbreak|do\s+anything\s+now|\bDAN\b|developer\s+mode)\b', re.I),
    re.compile(r'смени\s+роль', re.I),
)

# Бытовые «почему нет пункта / как сменить свой пароль» не входят сюда.
_ADMIN_HOWTO_PATTERNS = (
    re.compile(
        r'(как|how\s+to|comment)\s+.{0,40}(создать|удалить|заблокировать|create|delete|block)\s+'
        r'(пользовател|учётн|учетн|аккаунт|user\s+account|\buser\b)',
        re.I,
    ),
    re.compile(
        r'(назначить|выдать|сменить|поменять|assign|grant|change)\s+'
        r'(пользовател\w*\s+)?(роль|права|role|permission)',
        re.I,
    ),
    re.compile(
        r'(сброс\w*|reset)\s+(чуж\w+\s+)?(парол\w+|password)\s+'
        r'(пользовател|другому|для\s+пользовател|someone|another\s+user)',
        re.I,
    ),
    re.compile(
        r'(сброс\w*\s+парол\w+\s+(пользовател|другому)|reset\s+(a\s+|the\s+)?user\'?s?\s+password)',
        re.I,
    ),
    re.compile(
        r'(журнал\s+аудита|смотреть\s+аудит|открыть\s+аудит|audit\s+log|'
        r'как\s+.{0,30}аудит)',
        re.I,
    ),
    re.compile(
        r'(как|how\s+to).{0,40}(приглашен|invitation\s+link|send\s+invit)',
        re.I,
    ),
    re.compile(
        r'(как|how\s+to).{0,40}(админ[- ]панел|admin\s+panel|панель\s+админ)',
        re.I,
    ),
    re.compile(
        r'(править|изменить|настроить)\s+(системн\w+\s+)?меню',
        re.I,
    ),
)

_EVERYDAY_ALLOW_PATTERNS = (
    re.compile(r'почему\s+(у\s+меня\s+)?(нет|не\s+(вижу|виден|показывает))', re.I),
    re.compile(r'(where\s+is|why\s+(don\'t|do\s+not)\s+i\s+(see|have)|pourquoi)', re.I),
    re.compile(r'(свой|мой|моего)\s+парол', re.I),
    re.compile(r'(my|own)\s+password', re.I),
    re.compile(r'(нет\s+доступа|не\s+хватает\s+прав|обратиться\s+к\s+администратор)', re.I),
)

_OUTPUT_LEAK_PATTERNS = (
    re.compile(r'админ[- ]панел\w*.{0,40}(пользовател|рол|аудит|приглашен)', re.I),
    re.compile(r'admin\s+panel.{0,40}(users?|roles?|audit|invitation)', re.I),
    re.compile(r'(откройте|зайдите\s+в|перейдите\s+в)\s+админ[- ]панел', re.I),
    re.compile(r'(open|go\s+to)\s+the\s+admin\s+panel', re.I),
    re.compile(r'(создайте|удалите|заблокируйте)\s+(пользовател|учётн|учетн)', re.I),
    re.compile(r'(create|delete|block)\s+(a\s+|the\s+)?user', re.I),
    re.compile(r'(назначьте|выдайте)\s+(ему\s+|пользовател\w*\s+)?роль', re.I),
    re.compile(r'(сбросьте|reset)\s+(ему\s+|пользовател\w*\s+|the\s+user\'?s?\s+)?парол', re.I),
    re.compile(r'журнал\s+аудита', re.I),
    re.compile(r'админ[- ]панел\w*\s*→', re.I),
)

_REFUSAL = {
    'ru': (
        'Этого я подсказать не могу: такие действия доступны только администратору. '
        'Если нужного раздела нет в вашем меню, обратитесь к администратору системы.'
    ),
    'en': (
        'I cannot help with that: those actions are available only to an administrator. '
        'If you do not see the section in your menu, ask your system administrator.'
    ),
    'fr': (
        'Je ne peux pas aider pour cela : ces actions sont réservées à l’administrateur. '
        'Si la section n’apparaît pas dans votre menu, contactez l’administrateur du système.'
    ),
}


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str = ''


def refusal_text(ui_language: str) -> str:
    key = (ui_language or 'ru').strip().lower().split('-', 1)[0]
    return _REFUSAL.get(key) or _REFUSAL['ru']


def _normalize_text(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '')).strip()


def _is_everyday_allow(text: str) -> bool:
    return any(pattern.search(text) for pattern in _EVERYDAY_ALLOW_PATTERNS)


def inspect_input(text: str) -> SafetyDecision:
    blob = _normalize_text(text)
    if not blob:
        return SafetyDecision(True)
    if any(pattern.search(blob) for pattern in _JAILBREAK_PATTERNS):
        return SafetyDecision(False, REASON_JAILBREAK)
    if _is_everyday_allow(blob):
        return SafetyDecision(True)
    if any(pattern.search(blob) for pattern in _ADMIN_HOWTO_PATTERNS):
        return SafetyDecision(False, REASON_ADMIN_HOWTO)
    return SafetyDecision(True)


def inspect_output(text: str) -> SafetyDecision:
    blob = _normalize_text(text)
    if not blob:
        return SafetyDecision(True)
    if any(pattern.search(blob) for pattern in _OUTPUT_LEAK_PATTERNS):
        return SafetyDecision(False, REASON_OUTPUT_LEAK)
    return SafetyDecision(True)


def recent_user_texts(
    session,
    *,
    exclude_message_id=None,
    extra: Optional[Iterable[str]] = None,
) -> list[str]:
    texts: list[str] = []
    if session is not None:
        qs = session.messages.filter(
            message_type=ChatMessage.MESSAGE_TYPE_USER,
        ).order_by('-created_at')
        if exclude_message_id is not None:
            qs = qs.exclude(id=exclude_message_id)
        texts = [msg.content or '' for msg in qs[:_HISTORY_USER_LIMIT]]
        texts.reverse()
    if extra:
        texts.extend(item for item in extra if item)
    return texts


def evaluate_user_message(
    *,
    message: str,
    user,
    ui_language: str,
    session=None,
    exclude_message_id=None,
) -> Optional[str]:
    """None — можно вызывать модель. Иначе текст отказа."""
    if assistant_is_admin(user):
        return None
    combined = '\n'.join(
        recent_user_texts(
            session,
            exclude_message_id=exclude_message_id,
            extra=[message],
        )
    )
    decision = inspect_input(combined)
    if decision.allowed:
        return None
    return refusal_text(ui_language)


def filter_assistant_answer(
    *,
    answer: str,
    user,
    ui_language: str,
    knowledge_context: str = '',
) -> tuple[str, bool]:
    """Возвращает (текст, blocked). Админ не фильтруется по утечкам, но UI-grounding общий."""
    if not assistant_is_admin(user):
        decision = inspect_output(answer)
        if not decision.allowed:
            return refusal_text(ui_language), True
    grounded, blocked = filter_ungrounded_ui(
        answer,
        knowledge_context=knowledge_context,
        ui_language=ui_language,
    )
    if blocked:
        return grounded, True
    from src.core.cms.adp.services.permission_catalog import rewrite_slug_module_labels
    from src.core.utils.knowledge_pack import html_to_plain

    return rewrite_slug_module_labels(html_to_plain(grounded or answer)), False
