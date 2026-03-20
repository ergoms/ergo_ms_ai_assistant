import logging
import mimetypes
import os
from pathlib import Path
from urllib.parse import unquote

from django.conf import settings
from django.http import FileResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class GeneratedDocumentDownloadView(APIView):
    """
    GET /api/ai_assistant/documents/download/<path:file_path>
    Скачать сгенерированный документ
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, file_path):
        decoded_path = unquote(file_path)
        normalized_path = decoded_path.replace("/", os.sep)

        media_root = Path(settings.MEDIA_ROOT)
        full_path = media_root / normalized_path

        logger.info("Запрос скачивания: file_path=%s, full_path=%s", file_path, full_path)

        try:
            full_path = full_path.resolve()
            media_root = media_root.resolve()

            if not str(full_path).startswith(str(media_root)):
                return Response(
                    {"success": False, "error": "Недопустимый путь к файлу"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except Exception:
            return Response(
                {"success": False, "error": "Неверный путь к файлу"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not full_path.exists() or not full_path.is_file():
            logger.error("Файл не найден: %s", full_path)
            return Response(
                {"success": False, "error": f"Файл не найден: {full_path}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_size = full_path.stat().st_size
        logger.info("Размер файла: %s байт", file_size)

        if file_size == 0:
            logger.error("Файл пустой: %s", full_path)
            return Response(
                {"success": False, "error": "Файл пустой"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        content_type, _ = mimetypes.guess_type(str(full_path))
        if not content_type:
            content_type = "application/octet-stream"

        try:
            # FileResponse закрывает файловый дескриптор после отдачи ответа
            return FileResponse(
                full_path.open("rb"),
                content_type=content_type,
                as_attachment=True,
                filename=full_path.name,
            )
        except Exception as e:
            logger.error("Ошибка скачивания документа %s: %s", full_path, e)
            return Response(
                {"success": False, "error": f"Ошибка скачивания файла: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
