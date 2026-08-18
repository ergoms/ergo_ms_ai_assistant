"""
Реестр chat-профилей ModuleBridge.

Хост-модули регистрируют профиль через bridge.provide_many(CHAT_PROFILES_GROUP, …).
UI хаба/мини-чата остаётся в ai_assistant; ask делегируется в ask_stream_op хоста.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.core.integrations import bridge

# Межмодульная группа (не platform-контракт ядра). Дублируется строкой у потребителей.
CHAT_PROFILES_GROUP = 'ai_assistant.chat.profiles'

DEFAULT_PROFILE_ID = 'default'


def list_server_profiles() -> Dict[str, Dict[str, Any]]:
    """id → дескриптор профиля из bridge.all."""
    raw = bridge.all(CHAT_PROFILES_GROUP) or {}
    out: Dict[str, Dict[str, Any]] = {}
    for key, obj in raw.items():
        if not isinstance(obj, dict):
            continue
        profile_id = str(obj.get('id') or key).strip()
        if not profile_id or profile_id == DEFAULT_PROFILE_ID:
            continue
        ask_op = str(obj.get('ask_stream_op') or '').strip()
        if not ask_op:
            continue
        session_module = str(
            obj.get('session_module') or f'{profile_id}_chat'
        ).strip()
        mini_module = str(
            obj.get('mini_chat_module') or f'{profile_id}_mini'
        ).strip()
        perm_module = str(obj.get('permission_module') or '').strip()
        perm_key = str(obj.get('permission') or '').strip()
        out[profile_id] = {
            'id': profile_id,
            'ask_stream_op': ask_op,
            'session_module': session_module,
            'mini_chat_module': mini_module,
            'permission_module': perm_module,
            'permission': perm_key,
            'order': int(obj.get('order') or 100),
        }
    return out


def get_server_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    if not profile_id or profile_id == DEFAULT_PROFILE_ID:
        return None
    return list_server_profiles().get(str(profile_id).strip())
