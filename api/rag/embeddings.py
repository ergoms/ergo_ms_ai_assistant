"""
Сервис embeddings для RAG.

Имя библиотеки Ollama идёт в ollama_framework. Снимок Hugging Face org/name
считается локально через sentence-transformers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.utils.huggingface_snapshot import is_huggingface_repo_id

from ..ollama_gateway import LLMClientError, check_embeddings_health, embed_texts
from ..settings import RAG_VECTOR_DIMENSIONS
from .huggingface_embeddings import (
    HuggingFaceEmbeddingsError,
    check_health as check_huggingface_health,
    embed_texts as embed_huggingface_texts,
)

logger = logging.getLogger(__name__)


class EmbeddingsError(Exception):
    """Общее исключение для ошибок работы с embeddings."""


def pad_embedding(vector: List[float], dimensions: int = RAG_VECTOR_DIMENSIONS) -> List[float]:
    """Дополняет короткий вектор нулями до размера колонки pgvector."""
    if not isinstance(vector, list) or not all(isinstance(x, (int, float)) for x in vector):
        raise EmbeddingsError(
            f'Embedding неверного формата (ожидается список чисел): {type(vector)}'
        )
    length = len(vector)
    if length == dimensions:
        return [float(x) for x in vector]
    if length > dimensions:
        raise EmbeddingsError(
            f'Размерность embedding {length} больше колонки pgvector ({dimensions})'
        )
    return [float(x) for x in vector] + [0.0] * (dimensions - length)


class OllamaEmbeddingsService:
    """
    Сервис embeddings для RAG.

    Публичный API сохранён для совместимости с RAGIndexingService и RAGRetrievalService.
    """

    def __init__(
        self,
        base_url: str = 'http://localhost:11434',
        model: str = 'embeddinggemma',
        request_timeout: float = 30.0,
        ollama_config: Optional[Dict[str, Any]] = None,
    ):
        self._base_url = base_url.rstrip('/')
        self._model = model
        self._request_timeout = request_timeout
        self._ollama_config = dict(ollama_config or {})
        self._ollama_config.setdefault('base_url', self._base_url)
        self._ollama_config.setdefault('embeddings_model', self._model)
        self._use_huggingface = is_huggingface_repo_id(self._model)

    def _request_config(self) -> Dict[str, Any]:
        cfg = dict(self._ollama_config)
        cfg['base_url'] = self._base_url
        cfg['embeddings_model'] = self._model
        # Не тащить chat-model в map_ollama_config(embeddings=True).
        cfg.pop('model', None)
        return cfg

    def _embed(self, texts: List[str]) -> List[List[float]]:
        if self._use_huggingface:
            try:
                vectors = embed_huggingface_texts(texts, model_name=self._model)
            except HuggingFaceEmbeddingsError as exc:
                raise EmbeddingsError(str(exc)) from exc
        else:
            try:
                vectors = embed_texts(texts, ollama_config=self._request_config())
            except LLMClientError as exc:
                raise self._map_error(exc) from exc
        if not vectors:
            raise EmbeddingsError('Сервис embeddings вернул пустой список')
        return [pad_embedding(item) for item in vectors]

    def generate_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise EmbeddingsError('Текст не может быть пустым')
        vectors = self._embed([text.strip()])
        return vectors[0]

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        valid_texts = [text.strip() for text in texts if text and text.strip()]
        if not valid_texts:
            raise EmbeddingsError('Нет валидных текстов для обработки')

        embeddings = self._embed(valid_texts)
        if len(embeddings) != len(valid_texts):
            logger.warning(
                'Количество embeddings (%s) не совпадает с количеством текстов (%s)',
                len(embeddings),
                len(valid_texts),
            )
        return embeddings

    def check_health(self) -> Dict[str, Any]:
        if self._use_huggingface:
            return check_huggingface_health(self._model)
        return check_embeddings_health(
            base_url=self._base_url,
            model=self._model,
            ollama_config=self._request_config(),
        )

    def close(self) -> None:
        """Совместимость с прежним API — HTTP-клиент больше не создаётся локально."""

    def _map_error(self, exc: LLMClientError) -> EmbeddingsError:
        message = str(exc)
        if '404' in message or 'не найдена' in message.lower():
            return EmbeddingsError(
                f"Модель '{self._model}' не найдена. "
                f'Установите модель командой: ollama pull {self._model}\n'
                f'Рекомендуемые модели: embeddinggemma, qwen3-embedding, all-minilm, '
                f'deepvk/USER-bge-m3\n'
                f'Модель можно изменить через переменную окружения OLLAMA_EMBEDDINGS_MODEL'
            )
        if 'подключ' in message.lower() or 'connect' in message.lower():
            return EmbeddingsError(f'Не удалось подключиться к Ollama по адресу {self._base_url}')
        if 'таймаут' in message.lower() or 'timeout' in message.lower():
            return EmbeddingsError(f'Таймаут при генерации embeddings (>{self._request_timeout}s)')
        return EmbeddingsError(message)
