# -*- coding: utf-8 -*-
"""
BI-анализ через Polars + LLM — функциональность находится в разработке.
Файл оставлен как стаб для совместимости импортов.
"""
from django.conf import settings

from . import assistant_settings

DEFAULT_MODEL: str = getattr(settings, "OLLAMA_DEFAULT_MODEL", assistant_settings.OLLAMA_DEFAULT_MODEL)
OLLAMA_BASE_URL: str = getattr(settings, "OLLAMA_BASE_URL", assistant_settings.OLLAMA_BASE_URL)


class FastBIService:
    """Заглушка сервиса BI-анализа. Функциональность в разработке."""

    def __init__(self, *args, **kwargs):
        pass
