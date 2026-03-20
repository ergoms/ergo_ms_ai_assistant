from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..bi_optional import FileUpload, _BI_AVAILABLE


class UserFilesListView(APIView):
    """
    GET /api/ai_assistant/files/
    Получить список загруженных файлов пользователя из BI модуля
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _BI_AVAILABLE or FileUpload is None:
            return Response(
                {"success": False, "error": "Модуль BI Analysis не подключён к системе"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        files = FileUpload.objects.filter(owner=request.user).order_by("-uploaded_at")
        data = []
        for f in files:
            data.append(
                {
                    "id": f.id,
                    "name": f.name,
                    "original_filename": f.original_filename,
                    "file_type": f.file_type,
                    "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
                    "file_path": f.file.path if f.file else None,
                }
            )
        return Response(
            {
                "success": True,
                "files": data,
                "count": len(data),
            }
        )


class BIQueryView(APIView):
    """
    POST /api/ai_assistant/bi_query/
    Навык BI-анализа табличных данных — находится в разработке.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return Response(
            {
                "success": False,
                "error": "Функциональность BI-анализа находится в разработке.",
                "in_development": True,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
