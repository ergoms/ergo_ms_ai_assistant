"""Эмбеддинги снимка Hugging Face (sentence-transformers) для RAG."""
from __future__ import annotations

import logging
import threading
from typing import Any

from src.core.utils.huggingface_snapshot import ensure_local_source

from ..settings import AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE

logger = logging.getLogger(__name__)

_load_lock = threading.Lock()
_ST_MODEL = None
_ST_MODEL_NAME: str | None = None
_ST_DEVICE: str | None = None


class HuggingFaceEmbeddingsError(Exception):
    """Ошибка загрузки или вызова снимка Hugging Face."""


def _resolve_device(requested: str) -> str:
    requested = (requested or 'auto').strip().lower()
    if requested == 'cpu':
        return 'cpu'
    if requested in ('cuda', 'gpu'):
        try:
            import torch
            return 'cuda' if torch.cuda.is_available() else 'cpu'
        except Exception:
            return 'cpu'
    try:
        import torch
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    except Exception:
        return 'cpu'


def get_sentence_transformer(
    model_name: str,
    *,
    device: str | None = None,
):
    """Singleton SentenceTransformer для имени org/name."""
    global _ST_MODEL, _ST_MODEL_NAME, _ST_DEVICE

    name = (model_name or '').strip()
    if not name:
        raise HuggingFaceEmbeddingsError('Не задано имя снимка Hugging Face')
    resolved_device = _resolve_device(device or AI_ASSISTANT_OLLAMA_COMPUTE_DEVICE)

    with _load_lock:
        if (
            _ST_MODEL is not None
            and _ST_MODEL_NAME == name
            and _ST_DEVICE == resolved_device
        ):
            return _ST_MODEL

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise HuggingFaceEmbeddingsError(
                'Пакет sentence-transformers не установлен. '
                'Выполните: ergoms python-install'
            ) from exc

        source = ensure_local_source(name)
        logger.info('Загрузка embedding-снимка %s на %s', source, resolved_device)
        try:
            _ST_MODEL = SentenceTransformer(source, device=resolved_device)
        except Exception as exc:
            if resolved_device != 'cpu':
                logger.warning('Снимок embeddings на CPU: %s', exc)
                _ST_MODEL = SentenceTransformer(source, device='cpu')
                resolved_device = 'cpu'
            else:
                raise HuggingFaceEmbeddingsError(str(exc)) from exc

        _ST_MODEL_NAME = name
        _ST_DEVICE = resolved_device
        return _ST_MODEL


def embed_texts(
    texts: list[str],
    *,
    model_name: str,
    normalize: bool = True,
    batch_size: int = 16,
) -> list[list[float]]:
    cleaned = [str(item or '').strip() for item in texts]
    if not cleaned:
        return []

    model = get_sentence_transformer(model_name)
    try:
        vectors = model.encode(
            cleaned,
            batch_size=max(1, batch_size),
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
    except Exception as exc:
        raise HuggingFaceEmbeddingsError(str(exc)) from exc

    rows: list[list[float]] = []
    if getattr(vectors, 'ndim', None) == 1:
        vectors = [vectors]
    for item in vectors:
        raw = item.tolist() if hasattr(item, 'tolist') else item
        rows.append([float(value) for value in raw])
    return rows


def check_health(model_name: str) -> dict[str, Any]:
    try:
        get_sentence_transformer(model_name)
    except HuggingFaceEmbeddingsError as exc:
        return {
            'available': False,
            'model': model_name,
            'model_available': False,
            'backend': 'huggingface',
            'error': str(exc),
        }
    return {
        'available': True,
        'model': model_name,
        'model_available': True,
        'backend': 'huggingface',
    }
