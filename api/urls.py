from django.urls import path, re_path
from rest_framework.routers import DefaultRouter
from .views import (
    OllamaStatusView,
    ChatView, ChatStreamView, ChatSessionViewSet, KnowledgeDocumentViewSet,
    EmbeddingsStatusView, GeneratedDocumentDownloadView,
)
from .views.chat_views import MessageFeedbackView

router = DefaultRouter()
router.register(r'chat_sessions', ChatSessionViewSet, basename='chat-session')
router.register(r'knowledge_documents', KnowledgeDocumentViewSet, basename='knowledge-document')

urlpatterns = [
    path('ollama_status/', OllamaStatusView.as_view(), name='ai-assistant-ollama-status'),
    path('embeddings_status/', EmbeddingsStatusView.as_view(), name='ai-assistant-embeddings-status'),
    path('chat/', ChatView.as_view(), name='ai-assistant-chat'),
    path('chat/stream/', ChatStreamView.as_view(), name='ai-assistant-chat-stream'),
    path('messages/<uuid:message_id>/feedback/', MessageFeedbackView.as_view(), name='ai-assistant-message-feedback'),
    re_path(r'^documents/download/(?P<file_path>.+)$', GeneratedDocumentDownloadView.as_view(), name='ai-assistant-document-download'),
] + router.urls
