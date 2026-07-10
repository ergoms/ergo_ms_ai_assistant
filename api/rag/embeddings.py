"""
Сервис embeddings для RAG — делегирует в ollama_framework через ollama_gateway.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from modules.ollama_framework.api.client.base import LLMClientError

from ..ollama_gateway import check_embeddings_health, embed_texts

logger = logging.getLogger(__name__)


class EmbeddingsError(Exception):
    """Общее исключение для ошибок работы с embeddings."""

    pass


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

    def _request_config(self) -> Dict[str, Any]:
        cfg = dict(self._ollama_config)
        cfg['base_url'] = self._base_url
        cfg['embeddings_model'] = self._model
        return cfg

    def generate_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise EmbeddingsError('Текст не может быть пустым')

        try:
            vectors = embed_texts([text.strip()], ollama_config=self._request_config())
        except LLMClientError as exc:
            raise self._map_error(exc) from exc

        if not vectors:
            raise EmbeddingsError('Ollama вернул пустой список embeddings')

        embedding = vectors[0]
        if not isinstance(embedding, list) or not all(isinstance(x, (int, float)) for x in embedding):
            raise EmbeddingsError(
                f'Ollama вернул embedding неверного формата (ожидается список чисел): {type(embedding)}'
            )
        return embedding

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        valid_texts = [text.strip() for text in texts if text and text.strip()]
        if not valid_texts:
            raise EmbeddingsError('Нет валидных текстов для обработки')

        try:
            embeddings = embed_texts(valid_texts, ollama_config=self._request_config())
        except LLMClientError as exc:
            raise self._map_error(exc) from exc

        if not embeddings:
            raise EmbeddingsError('Ollama вернул пустой список embeddings')

        if len(embeddings) != len(valid_texts):
            logger.warning(
                'Количество embeddings (%s) не совпадает с количеством текстов (%s)',
                len(embeddings),
                len(valid_texts),
            )

        return embeddings

    def check_health(self) -> Dict[str, Any]:
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
                f'Рекомендуемые модели: embeddinggemma, qwen3-embedding, all-minilm\n'
                f'Модель можно изменить через переменную окружения OLLAMA_EMBEDDINGS_MODEL'
            )
        if 'подключ' in message.lower() or 'connect' in message.lower():
            return EmbeddingsError(f'Не удалось подключиться к Ollama по адресу {self._base_url}')
        if 'таймаут' in message.lower() or 'timeout' in message.lower():
            return EmbeddingsError(f'Таймаут при генерации embeddings (>{self._request_timeout}s)')
        return EmbeddingsError(message)
