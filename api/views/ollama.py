from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from src.core.utils.mixins import SwaggerSafeMixin

from ..ollama_gateway import LLMClientError, check_health
from ..permissions import CanViewAiAssistant
from .helpers import _get_rag_services


class OllamaStatusView(SwaggerSafeMixin, APIView):
    """
    GET /api/ai_assistant/ollama_status/

    Proxy статуса Ollama через gateway модуля (без прямого REST к ollama_framework).
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]

    def get(self, request):
        if self.is_swagger_fake_view():
            return Response({'available': False})

        try:
            health = check_health()
            return Response(health, status=status.HTTP_200_OK)
        except LLMClientError as exc:
            return Response({
                'available': False,
                'error': str(exc),
                'message': str(exc),
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({
                'available': False,
                'error': str(exc),
                'message': str(exc),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmbeddingsStatusView(SwaggerSafeMixin, APIView):
    """
    GET /api/ai_assistant/embeddings_status/
    Проверить доступность сервиса embeddings
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]

    def get(self, request):
        if self.is_swagger_fake_view():
            return Response({'success': True, 'available': False})

        try:
            embeddings_service, _ = _get_rag_services()
            health = embeddings_service.check_health()

            return Response({
                'success': True,
                **health,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'available': False,
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
