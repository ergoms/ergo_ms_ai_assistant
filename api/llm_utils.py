"""
Re-export gateway для обратной совместимости импортов.
"""
from modules.ollama_framework.api.client.base import LLMClientError
from modules.ollama_framework.api.config import RuntimeLLMConfig

from . import settings as ai_settings
from .ollama_gateway import (
    check_health,
    create_llm_client,
    create_llm_client as create_ollama_client,
    embed_texts,
    map_ollama_config,
)

DEFAULT_MODEL: str = ai_settings.OLLAMA_DEFAULT_MODEL
OLLAMA_BASE_URL: str = ai_settings.OLLAMA_BASE_URL

__all__ = [
    'DEFAULT_MODEL',
    'LLMClientError',
    'OLLAMA_BASE_URL',
    'RuntimeLLMConfig',
    'check_health',
    'create_llm_client',
    'create_ollama_client',
    'embed_texts',
    'map_ollama_config',
]
