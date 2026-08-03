"""Представления API модуля ai_assistant."""

from .ollama import EmbeddingsStatusView, OllamaStatusView
from .chat import ChatView
from .chat_stream import ChatStreamView
from .chat_sessions import ChatSessionViewSet
from .knowledge import GeneratedDocumentDownloadView, KnowledgeDocumentViewSet

__all__ = [
    'OllamaStatusView',
    'EmbeddingsStatusView',
    'ChatView',
    'ChatStreamView',
    'ChatSessionViewSet',
    'KnowledgeDocumentViewSet',
    'GeneratedDocumentDownloadView',
]
