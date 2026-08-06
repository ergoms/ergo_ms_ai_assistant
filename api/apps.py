"""
Конфигурация Django приложения для AI Assistant.
"""

from django.apps import AppConfig


class AiAssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.ai_assistant.api'
    label = 'ai_assistant'
    verbose_name = 'AI-ассистент'

    def ready(self):
        import modules.ai_assistant.api.models  # noqa
        from . import integrations  # noqa: F401
