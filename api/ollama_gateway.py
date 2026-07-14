"""
Единая точка доступа ai_assistant к ollama_framework.

Все вызовы Ollama из модуля идут через этот gateway (ModuleBridge или REST).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from modules.ollama_framework.api.client.base import BaseLLMClient, LLMClientError
from modules.ollama_framework.api.client.factory import create_client
from modules.ollama_framework.api.config import RuntimeLLMConfig

from . import settings as ai_settings

__all__ = [
    'LLMClientError',
    'RuntimeLLMConfig',
    'create_llm_client',
    'check_health',
    'check_embeddings_health',
    'embed_texts',
    'get_transport',
    'map_ollama_config',
]


def _invoke(operation: str, **kwargs):
    if get_transport() == 'http':
        from modules.ollama_framework.api.transport.dispatcher import ollama_invoke

        return ollama_invoke(operation, transport='http', **kwargs)
    from modules.ollama_framework.api.transport.local import invoke_local

    return invoke_local(operation, **kwargs)


def get_transport() -> str:
    transport = getattr(ai_settings, 'OLLAMA_FRAMEWORK_TRANSPORT', None) or 'local'
    mode = transport.strip().lower()
    if mode not in ('local', 'http'):
        raise LLMClientError(
            f'Недопустимый OLLAMA_FRAMEWORK_TRANSPORT={mode!r}. Допустимо: local, http.'
        )
    return mode


def map_ollama_config(
    ollama_config: Optional[Dict[str, Any]] = None,
    *,
    embeddings: bool = False,
) -> Dict[str, Any]:
    """Преобразует ollama_config из запроса клиента в overrides для ollama_framework."""
    cfg = dict(ollama_config or {})
    cfg.setdefault('provider', 'ollama')

    if embeddings:
        model = (
            cfg.pop('embeddings_model', None)
            or cfg.get('model')
            or ai_settings.OLLAMA_EMBEDDINGS_MODEL
        )
    else:
        model = cfg.get('model') or ai_settings.OLLAMA_DEFAULT_MODEL

    cfg['model'] = model
    cfg.setdefault('base_url', ai_settings.OLLAMA_BASE_URL)
    return cfg


def create_llm_client(
    ollama_config: Optional[Dict[str, Any]] = None,
    skip_env_injection: bool = False,
) -> Tuple[RuntimeLLMConfig, BaseLLMClient]:
    """Клиент для generate/chat/stream — через фабрику ollama_framework."""
    cfg = map_ollama_config(ollama_config, embeddings=False)
    return create_client(cfg, skip_env_injection=skip_env_injection)


def check_health(
    ollama_config: Optional[Dict[str, Any]] = None,
    *,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = map_ollama_config(ollama_config, embeddings=False)
    if model:
        cfg['model'] = model
    return _invoke(
        'health',
        config=cfg,
        skip_env_injection=bool(ollama_config),
    )


def check_embeddings_health(
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    ollama_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = map_ollama_config(ollama_config, embeddings=True)
    if base_url:
        cfg['base_url'] = base_url.rstrip('/')
    if model:
        cfg['model'] = model

    health = _invoke(
        'health',
        config=cfg,
        skip_env_injection=bool(ollama_config or base_url or model),
    )
    models = health.get('models') or []
    embed_model = cfg['model']
    model_available = bool(health.get('model_loaded')) or any(
        embed_model in m or m.startswith(embed_model) for m in models
    )

    result: Dict[str, Any] = {
        'available': bool(health.get('available')),
        'model': embed_model,
        'model_available': model_available,
        'base_url': health.get('base_url') or cfg.get('base_url'),
        'available_models': models,
    }
    if not result['available']:
        result['error'] = health.get('error') or health.get('message')
    return result


def embed_texts(
    texts: List[str],
    *,
    ollama_config: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> List[List[float]]:
    cfg = map_ollama_config(ollama_config, embeddings=True)
    kwargs: Dict[str, Any] = {'texts': texts}
    if model:
        kwargs['model'] = model
    return _invoke(
        'embed',
        config=cfg,
        skip_env_injection=bool(ollama_config),
        **kwargs,
    )
