"""
Единая точка доступа ai_assistant к ollama_framework.

Все вызовы — через ModuleBridge (local) или REST API модуля (http).
Прямые импорты modules.ollama_framework запрещены (modules.mdc).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from src.core.integrations import bridge

from . import settings as ai_settings

logger = logging.getLogger(__name__)

__all__ = [
    'LLMClientError',
    'check_health',
    'check_embeddings_health',
    'embed_texts',
    'chat',
    'get_transport',
    'map_ollama_config',
    'resolved_model',
]


class LLMClientError(RuntimeError):
    """Ошибка вызова ollama_framework из ai_assistant."""


_OPERATION_PATHS = {
    'health': 'status/',
    'list_models': 'models/',
    'generate': 'generate/',
    'chat': 'chat/',
    'embed': 'embed/',
}

_GET_OPERATIONS = frozenset({'health', 'list_models'})


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

    if 'compute_device' not in cfg and 'num_gpu' not in cfg:
        module_device = getattr(ai_settings, 'AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE', '')
        if module_device:
            cfg['compute_device'] = module_device

    return cfg


def resolved_model(
    ollama_config: Optional[Dict[str, Any]] = None,
    *,
    embeddings: bool = False,
) -> str:
    return str(map_ollama_config(ollama_config, embeddings=embeddings).get('model') or '')


def _api_base() -> str:
    base = (ai_settings.OLLAMA_FRAMEWORK_API_BASE or '').strip()
    if not base:
        raise LLMClientError(
            'OLLAMA_FRAMEWORK_API_BASE не задан. Укажите базовый URL API ERGO MS для режима http.'
        )
    base = base.rstrip('/') + '/'
    if 'ollama_framework' not in base:
        base = f'{base}ollama_framework/'
    return base


def _invoke_http(operation: str, **kwargs) -> Any:
    path = _OPERATION_PATHS.get(operation)
    if not path:
        raise LLMClientError(f'Неизвестная операция ollama_framework: {operation}')

    if kwargs.get('stream') or kwargs.get('stream_callback'):
        raise LLMClientError(
            'Streaming через OLLAMA_FRAMEWORK_TRANSPORT=http не поддерживается. '
            'Используйте transport=local (ModuleBridge).'
        )

    url = f'{_api_base()}{path}'
    headers = {'Content-Type': 'application/json'}
    auth_token = kwargs.pop('auth_token', None)
    if auth_token:
        headers['Authorization'] = f'Bearer {auth_token}'

    payload = dict(kwargs)
    timeout = float(getattr(ai_settings, 'AI_ASSISTANT_REQUEST_TIMEOUT', 180.0) or 180.0)

    try:
        if operation in _GET_OPERATIONS:
            params: Dict[str, str] = {}
            if payload.get('config') is not None:
                config = payload['config']
                params['config'] = (
                    config if isinstance(config, str) else json.dumps(config, ensure_ascii=False)
                )
            if payload.get('skip_env_injection'):
                params['skip_env_injection'] = '1'
            if params:
                url = f'{url}?{urlencode(params)}'
            response = httpx.get(url, headers=headers, timeout=min(timeout, 30.0))
        else:
            response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and 'result' in data:
            return data['result']
        return data
    except httpx.HTTPError as exc:
        logger.warning('HTTP ollama_framework (%s): %s', operation, exc)
        raise LLMClientError(f'HTTP ollama_framework/{operation} недоступен: {exc}') from exc


def _invoke(operation: str, **kwargs) -> Any:
    """Вызов операции ollama_framework: ModuleBridge (local) или REST (http)."""
    if get_transport() == 'http':
        return _invoke_http(operation, **kwargs)

    op_name = f'ollama_framework.{operation}'
    if not bridge.has(op_name):
        raise LLMClientError(
            f'Операция {op_name} недоступна. '
            'Убедитесь, что модуль ollama_framework установлен и загружен.'
        )
    try:
        return bridge.call(op_name, **kwargs)
    except Exception as exc:
        raise LLMClientError(str(exc)) from exc


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


def chat(
    messages: List[Dict[str, str]],
    *,
    ollama_config: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    stream: bool = False,
    stream_callback: Optional[Callable[[str], None]] = None,
    num_predict: Optional[int] = None,
    seed: Optional[int] = None,
    return_stats: bool = False,
) -> str | tuple[str, Dict[str, Any]]:
    """Chat через ModuleBridge / REST ollama_framework."""
    cfg = map_ollama_config(ollama_config, embeddings=False)
    result = _invoke(
        'chat',
        messages=messages,
        config=cfg,
        skip_env_injection=bool(ollama_config),
        temperature=temperature,
        stream=stream,
        stream_callback=stream_callback,
        num_predict=num_predict,
        seed=seed,
        return_stats=return_stats,
    )
    if isinstance(result, str):
        return result
    return result
