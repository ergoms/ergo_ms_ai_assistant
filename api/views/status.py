from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..llm_utils import DEFAULT_MODEL, create_ollama_client
from ..rag_service import get_rag_services


class OllamaStatusView(APIView):
    """
    GET /api/ai_assistant/ollama_status/
    Проверить доступность Ollama (быстрая проверка без загрузки модели)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            _, client = create_ollama_client({"model": DEFAULT_MODEL})
            health = client.check_health()
            if health.get("available"):
                return Response(
                    {
                        "available": True,
                        "message": "Ollama доступен",
                        "model": DEFAULT_MODEL,
                        "model_exists": health.get("model_loaded", False),
                        "available_models": health.get("models", []),
                    }
                )
            return Response(
                {
                    "available": False,
                    "message": health.get("error", "Ollama недоступен"),
                }
            )
        except Exception as e:
            return Response(
                {
                    "available": False,
                    "message": f"Ошибка подключения к Ollama: {str(e)}",
                }
            )


class EmbeddingsStatusView(APIView):
    """
    GET /api/ai_assistant/embeddings_status/
    Проверить доступность сервиса embeddings
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            embeddings_service, _ = get_rag_services()
            health = embeddings_service.check_health()
            return Response({"success": True, **health})
        except Exception as e:
            return Response(
                {
                    "success": False,
                    "available": False,
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
