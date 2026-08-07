import json
import math
import logging

import pandas as pd
import numpy as np

from ..rag import (
    OllamaEmbeddingsService,
    RAGRetrievalService,
    RAGRetrievalError,
    RetrievalScope,
)
from ..settings import (
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDINGS_MODEL,
    RAG_TOP_K,
    RAG_SIMILARITY_THRESHOLD,
    RAG_MAX_CONTEXT_LENGTH,
    RAG_ENABLED,
    RAG_INCLUDE_SYSTEM_IN_CHAT,
    RAG_SYSTEM_CORPUS_ENABLED,
    AI_ASSISTANT_REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)

def _sanitize_for_json(obj):
    """
    Рекурсивно очищает объект от значений, которые не поддерживаются JSON.
    NaN, Infinity, -Infinity заменяются на None.
    """
    # Ранний выход для простых типов
    if obj is None:
        return None
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='ignore')
    
    # Оптимизация для float - самый частый случай
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    
    # Оптимизация для numpy/pandas типов
    if isinstance(obj, (np.floating, np.integer)):
        if isinstance(obj, np.floating):
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        return int(obj)
    
    # Проверка на numpy arrays и pandas структуры - обрабатываем их отдельно
    if isinstance(obj, np.ndarray):
        return [_sanitize_for_json(item) for item in obj.tolist()]
    
    if isinstance(obj, pd.Series):
        return [_sanitize_for_json(item) for item in obj.tolist()]
    
    if isinstance(obj, pd.DataFrame):
        # DataFrame преобразуем в список словарей (records)
        return obj.replace({np.nan: None, pd.NA: None}).to_dict(orient='records')
    
    # Проверка на NaN/None только для скалярных значений (не массивов)
    # pd.isna() для массивов возвращает массив, что вызывает ошибку в if
    try:
        if not isinstance(obj, (list, tuple, dict, np.ndarray, pd.Series, pd.DataFrame)):
            if pd.isna(obj):
                return None
    except (TypeError, ValueError):
        # Если pd.isna() не может обработать тип, пропускаем
        pass
    
    # Словари
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    
    # Списки
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    
    # Для остальных типов пробуем преобразовать в строку
    try:
        return str(obj)
    except Exception:
        return None


def _safe_json_dumps(obj, **kwargs):
    """Безопасная JSON сериализация с обработкой NaN/Infinity."""
    # Оптимизированные параметры JSON для скорости
    default_kwargs = {
        'ensure_ascii': False,
        'separators': (',', ':'),  # Без пробелов - быстрее и меньше размер
        'check_circular': False,   # Если уверены, что нет циклов
    }
    default_kwargs.update(kwargs)
    return json.dumps(_sanitize_for_json(obj), **default_kwargs)




# Глобальные экземпляры RAG сервисов (ленивая инициализация)
_rag_embeddings_service: OllamaEmbeddingsService | None = None
_rag_retrieval_service: RAGRetrievalService | None = None


def _get_rag_services(ollama_config=None):
    """
    Получает или создает RAG сервисы (embeddings и retrieval)
    
    Args:
        ollama_config: Настройки Ollama (опционально, берет из config если не указано)
        
    Returns:
        Кортеж (embeddings_service, retrieval_service)
    """
    global _rag_embeddings_service, _rag_retrieval_service
    
    from ..ollama_gateway import map_ollama_config

    # base_url и модель embeddings — только из серверного map (не из сырого клиента).
    mapped = map_ollama_config(ollama_config, embeddings=True)
    base_url = mapped.get('base_url') or OLLAMA_BASE_URL
    embeddings_model = mapped.get('model') or OLLAMA_EMBEDDINGS_MODEL

    # Создаем или обновляем сервисы если настройки изменились
    if (_rag_embeddings_service is None or
        _rag_embeddings_service._base_url != base_url or
        _rag_embeddings_service._model != embeddings_model):
        _rag_embeddings_service = OllamaEmbeddingsService(
            base_url=base_url,
            model=embeddings_model,
            request_timeout=AI_ASSISTANT_REQUEST_TIMEOUT,
            ollama_config=mapped,
        )
    
    if _rag_retrieval_service is None:
        _rag_retrieval_service = RAGRetrievalService(
            embeddings_service=_rag_embeddings_service,
            top_k=RAG_TOP_K,
            similarity_threshold=RAG_SIMILARITY_THRESHOLD,
        )
    else:
        _rag_retrieval_service.embeddings_service = _rag_embeddings_service
        _rag_retrieval_service.top_k = RAG_TOP_K
        _rag_retrieval_service.similarity_threshold = RAG_SIMILARITY_THRESHOLD
    
    return _rag_embeddings_service, _rag_retrieval_service


def _get_rag_context(
    query: str,
    user,
    ollama_config=None,
    enabled=None,
    document_ids=None,
    include_system=None,
    system_only=False,
    scopes=None,
):
    """
    Получает контекст из базы знаний RAG для запроса пользователя.

    scopes — список RetrievalScope для объединённого поиска (один embed).
    """
    if enabled is None:
        enabled = RAG_ENABLED

    if not enabled:
        return '', []

    if include_system is None:
        include_system = (
            RAG_SYSTEM_CORPUS_ENABLED
            and RAG_INCLUDE_SYSTEM_IN_CHAT
            and not document_ids
            and not system_only
        )

    try:
        embeddings_service, retrieval_service = _get_rag_services(ollama_config)

        if scopes:
            context, chunks = retrieval_service.retrieve_multi_scope_context(
                query,
                scopes,
                max_context_length=RAG_MAX_CONTEXT_LENGTH,
            )
            return context, chunks

        context, chunks = retrieval_service.retrieve_and_build_context(
            query=query,
            user=user,
            max_context_length=RAG_MAX_CONTEXT_LENGTH,
            document_ids=document_ids,
            include_system=include_system,
            system_only=system_only,
        )

        return context, chunks

    except RAGRetrievalError as e:
        logger.warning('Ошибка RAG retrieval: %s', e)
        return '', []
    except Exception as e:
        logger.error('Неожиданная ошибка RAG retrieval: %s', e, exc_info=True)
        return '', []


