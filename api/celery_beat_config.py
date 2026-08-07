"""Расписание Celery Beat для ai_assistant (ежедневный sync корпуса RAG)."""

from typing import Any, Dict

from celery.schedules import crontab

from src.core.utils.celery_beat.base import CeleryBeatModuleConfig

from .settings import RAG_SYSTEM_CORPUS_BEAT_ENABLED, RAG_SYSTEM_CORPUS_ENABLED


class AiAssistantCeleryBeatConfig(CeleryBeatModuleConfig):
    def get_beat_schedule(self) -> Dict[str, Dict[str, Any]]:
        if not RAG_SYSTEM_CORPUS_ENABLED or not RAG_SYSTEM_CORPUS_BEAT_ENABLED:
            return {}
        return {
            'ai_assistant-sync-system-knowledge-daily': {
                'task': 'modules.ai_assistant.api.tasks.sync_system_knowledge_task',
                'schedule': crontab(hour=3, minute=0),
                'options': {'queue': 'ai_assistant'},
            },
        }
