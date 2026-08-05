"""Сбор загрузок: media_api (files_paths / file_path) или request.FILES."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from rest_framework.exceptions import ValidationError

from src.core.utils.mixins import MediaApiFileMixin, validate_media_path

from . import settings as ai_settings

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = frozenset({
    'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp',
})
DOCUMENT_EXTENSIONS = frozenset({
    'pdf', 'docx', 'doc', 'txt', 'md', 'markdown', 'csv', 'xlsx', 'xls',
})


def _parse_json_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def file_extension(name: str) -> str:
    return Path(name or '').suffix.lower().lstrip('.')


def is_image_upload(info: dict[str, Any]) -> bool:
    name = info.get('name') or ''
    path = info.get('file_path') or ''
    return file_extension(name) in IMAGE_EXTENSIONS or file_extension(path) in IMAGE_EXTENSIONS


def partition_upload_infos(
    upload_infos: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Разделяет загрузки на документы (RAG) и изображения (vision)."""
    documents: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    for info in upload_infos or []:
        if is_image_upload(info):
            images.append(info)
        else:
            documents.append(info)
    return documents, images


def build_attachments_metadata(
    document_infos: list[dict[str, Any]],
    image_infos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Метаданные вложений для ChatMessage (только media path, без base64)."""
    attachments: list[dict[str, Any]] = []
    for info in image_infos:
        path = info.get('file_path')
        if not path:
            continue
        attachments.append({
            'path': path,
            'name': info.get('name') or path.rsplit('/', 1)[-1],
            'kind': 'image',
        })
    for info in document_infos:
        path = info.get('file_path')
        if not path:
            # multipart fallback — path может отсутствовать
            attachments.append({
                'path': '',
                'name': info.get('name') or 'file',
                'kind': 'document',
            })
            continue
        attachments.append({
            'path': path,
            'name': info.get('name') or path.rsplit('/', 1)[-1],
            'kind': 'document',
        })
    return attachments


def load_images_base64_for_ollama(
    image_infos: list[dict[str, Any]],
) -> list[str]:
    """
    Localize media_api paths → base64 для текущего запроса к Ollama.
    Multipart image без file_path не поддерживается как основной канал.
    """
    from .media_storage import localize_path

    max_images = max(1, int(getattr(ai_settings, 'AI_ASSISTANT_MAX_CHAT_IMAGES', 4)))
    max_bytes = max(1, int(getattr(ai_settings, 'AI_ASSISTANT_MAX_IMAGE_BYTES', 10 * 1024 * 1024)))

    images_b64: list[str] = []
    for info in image_infos[:max_images]:
        path = info.get('file_path')
        name = info.get('name') or 'image'
        if not path:
            logger.warning(
                'Изображение %s без media_api path пропущено (нужен files_paths)',
                name,
            )
            continue
        localized = localize_path(path)
        try:
            with open(localized.path, 'rb') as handle:
                raw = handle.read()
            if len(raw) > max_bytes:
                logger.warning(
                    'Изображение %s слишком большое (%s байт), пропуск',
                    name,
                    len(raw),
                )
                continue
            if not raw:
                logger.warning('Изображение %s пустое, пропуск', name)
                continue
            images_b64.append(base64.b64encode(raw).decode('ascii'))
        except Exception as exc:
            logger.error('Не удалось прочитать изображение %s: %s', name, exc, exc_info=True)
        finally:
            localized.release()

    skipped = len(image_infos) - max_images
    if skipped > 0:
        logger.warning('Пропущено %s изображений сверх лимита %s', skipped, max_images)
    return images_b64


def collect_chat_upload_infos(request) -> list[dict[str, Any]]:
    """
    Возвращает список:
    - {'name': str, 'file_path': str} — файл уже в media_api
    - {'name': str, 'file': UploadedFile} — multipart fallback (документы)
    """
    infos: list[dict[str, Any]] = []

    files_paths = _parse_json_list(request.data.get('files_paths'))
    if not files_paths:
        single_path = request.data.get('file_path')
        if single_path:
            files_paths = [{
                'path': single_path,
                'original_name': request.data.get('original_filename', ''),
            }]

    if files_paths:
        for item in files_paths:
            if isinstance(item, str):
                path = item
                original_name = path.rsplit('/', 1)[-1]
            elif isinstance(item, dict):
                path = item.get('path') or item.get('file_path')
                original_name = (
                    item.get('original_name')
                    or item.get('original_filename')
                    or (path.rsplit('/', 1)[-1] if path else 'file')
                )
            else:
                continue
            if not path:
                continue
            storage_path = validate_media_path(path, 'file')
            infos.append({'name': original_name, 'file_path': storage_path})
        return infos

    uploaded_files = request.FILES.getlist('files')
    if not uploaded_files:
        single_file = request.FILES.get('file')
        if single_file:
            uploaded_files = [single_file]
    for uploaded in uploaded_files:
        # Картинки через multipart не принимаем как основной канал.
        if file_extension(uploaded.name) in IMAGE_EXTENSIONS:
            logger.warning(
                'Изображение %s через multipart проигнорировано; нужен media_api files_paths',
                uploaded.name,
            )
            continue
        infos.append({'name': uploaded.name, 'file': uploaded})
    return infos


def assign_knowledge_file(document, *, file=None, file_path=None) -> None:
    """Присваивает FileField документа из upload или media path."""
    if not file and not file_path:
        raise ValidationError({'file': 'Не указан файл или file_path'})
    MediaApiFileMixin.assign_file_field(document, 'file', file=file, file_path=file_path)
    document.save(update_fields=['file'])


def extract_text_from_upload_info(info: dict[str, Any]) -> tuple[str, str]:
    """Извлекает текст из media path или UploadedFile. Возвращает (text, file_type)."""
    from .media_storage import parse_localized_document
    from .rag.parser import DocumentParserService

    name = info.get('name') or 'file'
    if info.get('file_path'):
        return parse_localized_document(info['file_path'], filename=name)

    uploaded = info.get('file')
    if not uploaded:
        raise ValidationError({'file': 'Пустая загрузка'})
    from io import BytesIO
    file_obj = BytesIO(uploaded.read())
    uploaded.seek(0)
    return DocumentParserService.parse_document(file_obj=file_obj, filename=name)


def create_temp_knowledge_document(*, user, session, info: dict[str, Any]):
    """Создаёт временный KnowledgeDocument для векторизации чата."""
    from django.utils import timezone
    from .models import KnowledgeDocument

    name = info.get('name') or 'file'
    doc = KnowledgeDocument.objects.create(
        user=user,
        corpus=KnowledgeDocument.CORPUS_USER,
        title=f"Временный документ: {name}",
        source=f"chat_upload_{session.id}",
        metadata={
            'session_id': str(session.id),
            'is_temporary': True,
            'uploaded_at': timezone.now().isoformat(),
        },
    )
    assign_knowledge_file(
        doc,
        file=info.get('file'),
        file_path=info.get('file_path'),
    )
    return doc
