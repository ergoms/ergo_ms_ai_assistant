"""
Единая точка доступа ai_assistant к ollama_framework.

Все вызовы — через ModuleBridge (local) или REST API модуля (http).
Прямые импорты modules.ollama_framework запрещены (modules.mdc).
"""
from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Optional
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
    'chat_stream',
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
    'chat_stream': 'chat/stream/',
    'embed': 'embed/',
}

_GET_OPERATIONS = frozenset({'health', 'list_models'})

_llm_slot_lock = threading.Lock()
_llm_slot_limit: Optional[int] = None
_llm_slots: Optional[threading.Semaphore] = None


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return max(1, int(default))
    return max(1, parsed)


def _concurrency_limit() -> int:
    return _positive_int(
        getattr(ai_settings, 'AI_ASSISTANT_CONCURRENCY_LIMIT', 2),
        2,
    )


def _get_llm_slots() -> threading.Semaphore:
    """Процессный лимит одновременных chat/embed (AI_ASSISTANT_CONCURRENCY_LIMIT)."""
    global _llm_slot_limit, _llm_slots
    limit = _concurrency_limit()
    with _llm_slot_lock:
        if _llm_slots is None or _llm_slot_limit != limit:
            _llm_slots = threading.Semaphore(limit)
            _llm_slot_limit = limit
            logger.info(
                'AI Assistant: лимит одновременных LLM-запросов = %s',
                limit,
            )
        return _llm_slots


@contextmanager
def _llm_slot():
    slots = _get_llm_slots()
    slots.acquire()
    try:
        yield
    finally:
        slots.release()


def get_transport() -> str:
    transport = getattr(ai_settings, 'OLLAMA_FRAMEWORK_TRANSPORT', None) or 'local'
    mode = transport.strip().lower()
    if mode not in ('local', 'http'):
        raise LLMClientError(
            f'Недопустимый OLLAMA_FRAMEWORK_TRANSPORT={mode!r}. Допустимо: local, http.'
        )
    return mode


# Разрешённые ключи из тела запроса клиента. base_url / compute / timeouts — только с сервера.
_CLIENT_OLLAMA_KEYS = frozenset({
    'model',
    'embeddings_model',
    'temperature',
    'context_window',
    'max_tokens',
    'num_predict',
    'seed',
    'format',
})


def map_ollama_config(
    ollama_config: Optional[Dict[str, Any]] = None,
    *,
    embeddings: bool = False,
) -> Dict[str, Any]:
    """Преобразует ollama_config из запроса клиента в overrides для ollama_framework.

    Клиентский dict проходит whitelist: base_url, compute_device, num_gpu и лимиты
    нагрузки всегда берутся из .env модуля (защита от SSRF / обхода локального Ollama).
    """
    raw = ollama_config if isinstance(ollama_config, dict) else {}
    cfg = {
        key: raw[key]
        for key in _CLIENT_OLLAMA_KEYS
        if key in raw and raw[key] is not None
    }
    cfg['provider'] = 'ollama'

    if embeddings:
        # Не использовать chat-model из запроса (mistral и т.п.) — у них /api/embed → 501.
        model = (
            cfg.pop('embeddings_model', None)
            or ai_settings.OLLAMA_EMBEDDINGS_MODEL
        )
        cfg.pop('model', None)
    else:
        model = cfg.get('model') or ai_settings.OLLAMA_DEFAULT_MODEL

    cfg['model'] = model
    # Всегда серверный URL — клиентский base_url игнорируется.
    cfg['base_url'] = ai_settings.OLLAMA_BASE_URL

    module_device = getattr(ai_settings, 'AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE', '')
    if module_device:
        cfg['compute_device'] = module_device
    cfg.pop('num_gpu', None)

    # Лимиты нагрузки — только из .env модуля, не из тела запроса клиента.
    cfg['concurrency_limit'] = _concurrency_limit()
    try:
        cfg['max_retries'] = max(0, int(getattr(ai_settings, 'AI_ASSISTANT_MAX_RETRIES', 2)))
    except (TypeError, ValueError):
        cfg['max_retries'] = 2
    cfg['keep_alive'] = str(
        getattr(ai_settings, 'AI_ASSISTANT_KEEP_ALIVE', None) or '10m'
    )
    cfg['request_timeout'] = float(
        getattr(ai_settings, 'AI_ASSISTANT_REQUEST_TIMEOUT', 180.0) or 180.0
    )
    cfg['stream_timeout'] = float(
        getattr(ai_settings, 'AI_ASSISTANT_STREAM_TIMEOUT', 300.0) or 300.0
    )

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
    embed_model = model or cfg.get('model') or ai_settings.OLLAMA_EMBEDDINGS_MODEL
    cfg['model'] = embed_model
    with _llm_slot():
        return _invoke(
            'embed',
            texts=texts,
            model=embed_model,
            config=cfg,
            skip_env_injection=True,
        )


def chat(
    messages: List[Dict[str, Any]],
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
    with _llm_slot():
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


def chat_stream(
    messages: List[Dict[str, Any]],
    *,
    ollama_config: Optional[Dict[str, Any]] = None,
    temperature: Optional[float] = None,
    num_predict: Optional[int] = None,
    seed: Optional[int] = None,
) -> Iterator[str]:
    """Потоковый chat через ModuleBridge."""
    if get_transport() == 'http':
        raise LLMClientError(
            'Streaming через OLLAMA_FRAMEWORK_TRANSPORT=http не поддерживается. '
            'Используйте transport=local (ModuleBridge).'
        )
    cfg = map_ollama_config(ollama_config, embeddings=False)
    op_name = 'ollama_framework.chat_stream'
    if not bridge.has(op_name):
        raise LLMClientError(
            f'Операция {op_name} недоступна. '
            'Убедитесь, что модуль ollama_framework установлен и загружен.'
        )
    with _llm_slot():
        try:
            stream = bridge.call(
                op_name,
                messages=messages,
                config=cfg,
                skip_env_injection=bool(ollama_config),
                temperature=temperature,
                num_predict=num_predict,
                seed=seed,
            )
            yield from stream
        except Exception as exc:
            raise LLMClientError(str(exc)) from exc
