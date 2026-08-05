"""Очереди Celery для ai_assistant."""

from typing import Any, Dict

from src.core.utils.celery.base import CeleryModuleConfig


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
