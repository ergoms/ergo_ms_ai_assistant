"""
Re-export конфигурации LLM из ollama_framework.
"""
from modules.ollama_framework.api.config import (
    ComputeDevice,
    LLMProvider,
    RuntimeLLMConfig,
    build_runtime_config,
)

__all__ = [
    'ComputeDevice',
    'LLMProvider',
    'RuntimeLLMConfig',
    'build_runtime_config',
]
