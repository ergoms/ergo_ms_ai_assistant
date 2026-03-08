# -*- coding: utf-8 -*-
"""
BI-анализ через Polars + LLM — функциональность находится в разработке.
Файл оставлен как стаб для совместимости импортов.
"""
from django.conf import settings

DEFAULT_MODEL: str = getattr(settings, "OLLAMA_DEFAULT_MODEL", "mistral")
OLLAMA_BASE_URL: str = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")


class FastBIService:
    """Заглушка сервиса BI-анализа. Функциональность в разработке."""

    def __init__(self, *args, **kwargs):
        pass
