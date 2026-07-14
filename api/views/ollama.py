from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from ..ollama_gateway import check_health
from ..settings import OLLAMA_DEFAULT_MODEL
from .helpers import _get_rag_services

class OllamaStatusView(APIView):
    """
    GET /api/ai_assistant/ollama_status/
    Проверить доступность Ollama (быстрая проверка без загрузки модели)
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            health = check_health(model=OLLAMA_DEFAULT_MODEL)

            if health.get('available'):
                return Response({
                    'available': True,
                    'message': health.get('message', 'Ollama доступен'),
                    'model': OLLAMA_DEFAULT_MODEL,
                    'model_exists': health.get('model_loaded', False),
                    'available_models': health.get('models', []),
                })
            else:
                return Response({
                    'available': False,
                    'message': health.get('error', health.get('message', 'Ollama недоступен')),
                })
        except Exception as e:
            return Response({
                'available': False,
                'message': f'Ошибка подключения к Ollama: {str(e)}'
            })


class EmbeddingsStatusView(APIView):
    """
    GET /api/ai_assistant/embeddings_status/
    Проверить доступность сервиса embeddings
    """
    permission_classes = [permissions.IsAuthenticated]
    
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

