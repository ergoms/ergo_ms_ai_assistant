"""Роль собеседника для промпта и защиты выдачи. Только сервер, не клиент."""
from __future__ import annotations


def assistant_is_admin(user) -> bool:
    """Глобальный администратор через PermissionService, не флаги клиента."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    try:
        from src.core.cms.adp.services.permissions import PermissionService

        return bool(PermissionService.is_admin(user))
    except Exception:
        return False
