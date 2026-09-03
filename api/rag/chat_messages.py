"""
Сборка messages для Ollama chat: system prompt, runtime, RAG, история, файлы.
Общий путь для sync и stream chat views.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..file_uploads import (
    build_attachments_metadata,
    create_temp_knowledge_document,
    extract_text_from_upload_info,
    load_images_base64_for_ollama,
    partition_upload_infos,
)
from ..models import ChatMessage
from ..settings import (
    RAG_INCLUDE_SYSTEM_IN_CHAT,
    RAG_SYSTEM_CORPUS_ENABLED,
)
from .parser import DocumentParseError
from .prompts import (
    build_language_instruction,
    build_runtime_context,
    build_system_prompt,
    resolve_ui_language,
)
from .retrieval import RetrievalScope

logger = logging.getLogger(__name__)

__all__ = [
    'build_language_instruction',
    'build_ollama_messages',
    'build_runtime_context',
    'build_system_prompt',
    'resolve_rag_for_message',
    'resolve_ui_language',
]


def _history_user_content(msg: ChatMessage) -> str:
    """Текст user-сообщения для истории; картинки — только текстовая пометка."""
    content = msg.content or ''
    attachments = (msg.metadata or {}).get('attachments') or []
    image_names = [
        item.get('name') or 'image'
        for item in attachments
        if isinstance(item, dict) and item.get('kind') == 'image'
    ]
    if not image_names:
        return content
    notes = '\n'.join(f'[изображение: {name}]' for name in image_names)
    if content:
        return f'{notes}\n{content}'
    return notes


def _vectorize_uploads(
    *,
    user,
    session,
    upload_infos: List[dict],
    ollama_config,
    get_rag_services,
) -> List[str]:
    from ..indexing_queue import enqueue_knowledge_document_index

    new_ids: List[str] = []
    try:
        for info in upload_infos:
            name = info.get('name') or 'file'
            try:
                temp_doc = create_temp_knowledge_document(
                    user=user,
                    session=session,
                    info=info,
                )
                enqueue_knowledge_document_index(temp_doc, force=True)
                new_ids.append(str(temp_doc.id))
                logger.info('Файл %s поставлен в очередь индексации (ID: %s)', name, temp_doc.id)
            except Exception as exc:
                logger.error('Ошибка постановки файла %s в очередь индексации: %s', name, exc, exc_info=True)
    except Exception as exc:
        logger.error('Ошибка при векторизации файлов: %s', exc, exc_info=True)
    return new_ids


def _extract_file_context(upload_infos: List[dict]) -> str:
    file_contexts = []
    for info in upload_infos:
        name = info.get('name') or 'file'
        try:
            extracted_content, _detected_type = extract_text_from_upload_info(info)
            if extracted_content:
                max_len = 2000
                if len(extracted_content) > max_len:
                    extracted_content = extracted_content[:max_len] + '...'
                file_contexts.append(
                    f'[СОДЕРЖИМОЕ ФАЙЛА: {name}]\n{extracted_content}\n[/СОДЕРЖИМОЕ ФАЙЛА]'
                )
        except DocumentParseError as exc:
            logger.warning('Не удалось извлечь текст из файла %s: %s', name, exc)
        except Exception as exc:
            logger.error('Ошибка обработки файла %s: %s', name, exc, exc_info=True)
    if not file_contexts:
        return ''
    return (
        '\n\n'.join(file_contexts)
        + '\n\nИспользуй информацию из загруженных файлов для ответа на вопрос пользователя.'
    )


def resolve_rag_for_message(
    *,
    message: str,
    user,
    session,
    module: str,
    ollama_config,
    enable_vectorization: bool,
    vectorized_document_ids: List[str],
    request_document_id: Optional[str],
    get_rag_context,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Выбирает стратегию RAG и возвращает (context, chunks)."""
    include_system_default = RAG_SYSTEM_CORPUS_ENABLED and RAG_INCLUDE_SYSTEM_IN_CHAT
    scopes: List[RetrievalScope] = []

    if enable_vectorization and vectorized_document_ids:
        scopes.append(RetrievalScope(
            document_ids=vectorized_document_ids,
            user=user,
        ))
        if include_system_default:
            scopes.append(RetrievalScope(system_only=True, user=user))
        return get_rag_context(
            message,
            user=user,
            ollama_config=ollama_config,
            scopes=scopes,
        )

    document_id = None
    if session.metadata and session.metadata.get('document_id'):
        document_id = session.metadata['document_id']
    elif request_document_id:
        document_id = request_document_id

    if module == 'docs' and document_id:
        scopes.append(RetrievalScope(document_ids=[document_id], user=user))
        if include_system_default:
            scopes.append(RetrievalScope(system_only=True, user=user))
        return get_rag_context(
            message,
            user=user,
            ollama_config=ollama_config,
            scopes=scopes,
        )

    return get_rag_context(
        message,
        user=user,
        ollama_config=ollama_config,
        document_ids=None,
        include_system=include_system_default,
    )


def build_ollama_messages(
    *,
    message: str,
    user,
    session,
    module: str,
    upload_infos: Optional[List[dict]],
    enable_vectorization: bool,
    ollama_config,
    request_document_id: Optional[str],
    get_rag_services,
    get_rag_context,
    exclude_message_id=None,
    ui_language: str = 'ru',
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Собирает messages для ollama chat, RAG-chunks и metadata вложений.

    Картинки: media_api → base64 только для текущего user message (не в историю).
    Документы: inline text или vectorize → RAG.

    Returns:
        (messages, rag_chunks, attachments_metadata)
    """
    upload_infos = upload_infos or []
    document_infos, image_infos = partition_upload_infos(upload_infos)
    attachments_meta = build_attachments_metadata(document_infos, image_infos)

    vectorized_document_ids: List[str] = []
    if session.metadata and 'vectorized_documents' in session.metadata:
        vectorized_document_ids = list(session.metadata['vectorized_documents'])

    uploaded_file_context = ''
    if document_infos:
        if enable_vectorization:
            new_ids = _vectorize_uploads(
                user=user,
                session=session,
                upload_infos=document_infos,
                ollama_config=ollama_config,
                get_rag_services=get_rag_services,
            )
            if new_ids:
                if not session.metadata:
                    session.metadata = {}
                if 'vectorized_documents' not in session.metadata:
                    session.metadata['vectorized_documents'] = []
                session.metadata['vectorized_documents'].extend(new_ids)
                session.save(update_fields=['metadata'])
                vectorized_document_ids.extend(new_ids)
        else:
            uploaded_file_context = _extract_file_context(document_infos)

    rag_context, rag_chunks = resolve_rag_for_message(
        message=message,
        user=user,
        session=session,
        module=module,
        ollama_config=ollama_config,
        enable_vectorization=enable_vectorization,
        vectorized_document_ids=vectorized_document_ids,
        request_document_id=request_document_id,
        get_rag_context=get_rag_context,
    )

    images_b64 = load_images_base64_for_ollama(image_infos) if image_infos else []
    if images_b64:
        model_name = ''
        if isinstance(ollama_config, dict):
            model_name = str(ollama_config.get('model') or '')
        lowered = model_name.lower()
        vision_hints = ('llava', 'vision', 'moondream', 'minicpm-v', 'qwen2-vl', 'qwen2.5-vl')
        if model_name and not any(hint in lowered for hint in vision_hints):
            logger.warning(
                'К сообщению приложены изображения, модель %s может не поддерживать vision',
                model_name,
            )

    messages: List[Dict[str, Any]] = [
        {
            'role': 'system',
            'content': build_system_prompt(
                user=user,
                upload_infos=document_infos,
                enable_vectorization=enable_vectorization,
                ui_language=ui_language,
                has_images=bool(images_b64),
            ),
        }
    ]

    history_qs = session.messages.order_by('-created_at')
    if exclude_message_id is not None:
        history_qs = history_qs.exclude(id=exclude_message_id)
    recent = list(history_qs[:10])
    recent.reverse()
    for msg in recent:
        if msg.message_type == ChatMessage.MESSAGE_TYPE_USER:
            messages.append({'role': 'user', 'content': _history_user_content(msg)})
        elif msg.message_type == ChatMessage.MESSAGE_TYPE_ASSISTANT:
            messages.append({'role': 'assistant', 'content': msg.content})

    user_parts: List[str] = []
    if uploaded_file_context:
        user_parts.append(uploaded_file_context)
    if rag_context:
        from src.core.utils.knowledge_pack import html_to_plain

        rag_context = html_to_plain(rag_context)
        user_parts.append(
            f'[ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n{rag_context}\n[/ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n\n'
            'Используй эту информацию, чтобы подсказать пользователю по интерфейсу и возможностям системы. '
            'Называй только разделы, кнопки и поля, которые есть в этом блоке или в [ВОЗМОЖНОСТИ СИСТЕМЫ]. '
            'Если экрана или поля нет — так и скажи, не подбирай похожее название.'
        )
    user_parts.append(message)
    user_message: Dict[str, Any] = {
        'role': 'user',
        'content': '\n\n'.join(user_parts),
    }
    if images_b64:
        user_message['images'] = images_b64
    messages.append(user_message)

    return messages, rag_chunks, attachments_meta
