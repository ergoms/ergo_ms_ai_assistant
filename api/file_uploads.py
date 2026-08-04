"""Сбор загрузок: media_api (files_paths / file_path) или request.FILES."""

from __future__ import annotations

import json
from typing import Any

from rest_framework.exceptions import ValidationError

from src.core.utils.mixins import MediaApiFileMixin, validate_media_path


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


def collect_chat_upload_infos(request) -> list[dict[str, Any]]:
    """
    Возвращает список:
    - {'name': str, 'file_path': str} — файл уже в media_api
    - {'name': str, 'file': UploadedFile} — multipart fallback
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
