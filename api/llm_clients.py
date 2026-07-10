"""
Re-export типов LLM из ollama_framework для обратной совместимости.
"""
from modules.ollama_framework.api.client.base import BaseLLMClient, LLMClientError
from modules.ollama_framework.api.client.factory import build_llm_client
from modules.ollama_framework.api.config import RuntimeLLMConfig, build_runtime_config

__all__ = [
    'BaseLLMClient',
    'LLMClientError',
    'RuntimeLLMConfig',
    'build_llm_client',
    'build_runtime_config',
]
