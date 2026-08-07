"""Очереди Celery для ai_assistant (индексация RAG)."""

from typing import Any, Dict

from src.core.utils.celery.base import CeleryModuleConfig

from .settings import AI_ASSISTANT_CONCURRENCY_LIMIT


class AiAssistantCeleryConfig(CeleryModuleConfig):
    def get_task_routes(self) -> Dict[str, Dict[str, Any]]:
        return {
            'modules.ai_assistant.api.tasks.*': {'queue': 'ai_assistant'},
        }

    def get_task_queues(self) -> Dict[str, Dict[str, Any]]:
        return {
            'ai_assistant': {
                'exchange': 'ai_assistant',
                'routing_key': 'ai_assistant',
            },
        }

    def get_task_annotations(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def get_max_concurrent_tasks(self) -> int:
        """Лимит параллельной индексации в очереди ai_assistant."""
        return max(1, int(AI_ASSISTANT_CONCURRENCY_LIMIT or 1))
