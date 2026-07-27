from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from ..permissions import CanViewAiAssistant

from .helpers import _get_rag_services


class EmbeddingsStatusView(APIView):
    """
    GET /api/ai_assistant/embeddings_status/
    Проверить доступность сервиса embeddings
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]
    
    def get(self, request):
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
