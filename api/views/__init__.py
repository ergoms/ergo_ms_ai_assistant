"""HTTP views for ai_assistant API (split from former monolithic views.py)."""

from .bi_views import BIQueryView, UserFilesListView
from .chart_views import ChartAnalysisView
from .chat_views import ChatStreamView, ChatView
from .document_views import GeneratedDocumentDownloadView
from .knowledge_views import KnowledgeDocumentViewSet
from .session_views import ChatSessionViewSet
from .status import EmbeddingsStatusView, OllamaStatusView

__all__ = [
    "BIQueryView",
    "ChartAnalysisView",
    "ChatView",
    "ChatStreamView",
    "ChatSessionViewSet",
    "KnowledgeDocumentViewSet",
    "OllamaStatusView",
    "EmbeddingsStatusView",
    "GeneratedDocumentDownloadView",
    "UserFilesListView",
]
