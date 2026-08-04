"""
Сборка messages для Ollama chat: system prompt, runtime, RAG, история, файлы.
Общий путь для sync и stream chat views.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..file_uploads import (
    create_temp_knowledge_document,
    extract_text_from_upload_info,
)
from ..models import ChatMessage
from ..settings import (
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_INCLUDE_SYSTEM_IN_CHAT,
    RAG_SYSTEM_CORPUS_ENABLED,
)
from .indexing import RAGIndexingService
from .parser import DocumentParseError

logger = logging.getLogger(__name__)

ERGO_SYSTEM_PROMPT = """Ты — помощник пользователя сайта ERGO MS.

Твоя задача — объяснять функционал интерфейса простым языком: где что найти, как выполнить типичное действие, какие разделы для чего нужны.

Правила ответа:
1. Опирайся на блок [ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ], runtime-контекст и загруженные файлы пользователя.
2. Говори с точки зрения пользователя сайта (меню, кнопки, разделы, роли), а не разработчика.
3. Не упоминай ergoms, manage.py, .env, Docker, миграции, API, исходный код, ModuleBridge и внутреннюю архитектуру — если пользователь сам об этом не спросил явно.
4. Не выдумывай разделы, кнопки и права. Если в контексте нет ответа — скажи об этом и предложи уточнить вопрос или обратиться к администратору.
5. Если раздела нет в меню у пользователя — объясни, что доступ зависит от роли, и посоветуй администратора.
6. Отвечай кратко и по шагам, на языке пользователя.
"""


def build_runtime_context() -> str:
    """Краткий снимок возможностей системы для пользователя."""
    module_lines: list[str] = []
    try:
        from src.core.cms.adp.services.permission_catalog import get_modules_catalog

        for mod in get_modules_catalog(include_disabled=False):
            if mod.get('disabled'):
                continue
            label = (mod.get('module_label') or mod.get('module_name') or '').strip()
            if label:
                module_lines.append(label)
    except Exception as exc:
        logger.warning('Не удалось получить каталог модулей: %s', exc)
        try:
            from src.core.utils.module_registry import get_installed_module_names

            module_lines = list(get_installed_module_names())
        except Exception:
            module_lines = []

    modules_line = ', '.join(module_lines) if module_lines else '(список недоступен)'
    return (
        '[ВОЗМОЖНОСТИ САЙТА]\n'
        f'Установленные разделы/модули: {modules_line}\n'
        'Навигация — через боковое меню и меню пользователя в шапке.\n'
        'Доступ к разделам зависит от роли пользователя.\n'
        '[/ВОЗМОЖНОСТИ САЙТА]'
    )


def build_system_prompt(
    *,
    upload_infos: Optional[List[dict]] = None,
    enable_vectorization: bool = False,
) -> str:
    parts = [ERGO_SYSTEM_PROMPT.strip(), build_runtime_context()]
    if upload_infos:
        if enable_vectorization:
            parts.append(
                'Пользователь загрузил файлы; они проиндексированы для векторного поиска. '
                'Учитывай найденные фрагменты при ответе.'
            )
        else:
            parts.append(
                'Пользователь загрузил файлы. Используй их содержимое при ответе на вопросы.'
            )
    return '\n\n'.join(parts)


def _vectorize_uploads(
    *,
    user,
    session,
    upload_infos: List[dict],
    ollama_config,
    get_rag_services,
) -> List[str]:
    new_ids: List[str] = []
    try:
        embeddings_service, _ = get_rag_services(ollama_config)
        indexing_service = RAGIndexingService(
            embeddings_service=embeddings_service,
            chunk_size=RAG_CHUNK_SIZE,
            chunk_overlap=RAG_CHUNK_OVERLAP,
        )
        for info in upload_infos:
            name = info.get('name') or 'file'
            try:
                temp_doc = create_temp_knowledge_document(
                    user=user,
                    session=session,
                    info=info,
                )
                indexing_result = indexing_service.index_document(temp_doc, force_reindex=True)
                if indexing_result.get('success'):
                    new_ids.append(str(temp_doc.id))
                    logger.info('Файл %s проиндексирован (ID: %s)', name, temp_doc.id)
                else:
                    logger.warning(
                        'Не удалось проиндексировать файл %s: %s',
                        name,
                        indexing_result.get('error'),
                    )
                    temp_doc.delete()
            except Exception as exc:
                logger.error('Ошибка векторизации файла %s: %s', name, exc, exc_info=True)
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


def _merge_contexts(*parts: str) -> str:
    return '\n\n'.join(p for p in parts if p)


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

    if enable_vectorization and vectorized_document_ids:
        upload_ctx, upload_chunks = get_rag_context(
            query=message,
            user=user,
            ollama_config=ollama_config,
            document_ids=vectorized_document_ids,
            include_system=False,
        )
        system_ctx, system_chunks = ('', [])
        if include_system_default:
            system_ctx, system_chunks = get_rag_context(
                query=message,
                user=user,
                ollama_config=ollama_config,
                document_ids=None,
                include_system=False,
                system_only=True,
            )
        return _merge_contexts(upload_ctx, system_ctx), upload_chunks + system_chunks

    document_id = None
    if session.metadata and session.metadata.get('document_id'):
        document_id = session.metadata['document_id']
    elif request_document_id:
        document_id = request_document_id

    if module == 'docs' and document_id:
        doc_ctx, doc_chunks = get_rag_context(
            query=message,
            user=user,
            ollama_config=ollama_config,
            document_ids=[document_id],
            include_system=False,
        )
        system_ctx, system_chunks = ('', [])
        if include_system_default:
            system_ctx, system_chunks = get_rag_context(
                query=message,
                user=user,
                ollama_config=ollama_config,
                document_ids=None,
                include_system=False,
                system_only=True,
            )
        return _merge_contexts(doc_ctx, system_ctx), doc_chunks + system_chunks

    # Обычный chat / docs без document_id — system ∨ user KB
    return get_rag_context(
        query=message,
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
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Собирает messages для ollama chat и метаданные RAG-chunks.

    Returns:
        (messages, rag_chunks)
    """
    upload_infos = upload_infos or []
    vectorized_document_ids: List[str] = []
    if session.metadata and 'vectorized_documents' in session.metadata:
        vectorized_document_ids = list(session.metadata['vectorized_documents'])

    uploaded_file_context = ''
    if upload_infos:
        if enable_vectorization:
            new_ids = _vectorize_uploads(
                user=user,
                session=session,
                upload_infos=upload_infos,
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
            uploaded_file_context = _extract_file_context(upload_infos)

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

    messages: List[Dict[str, str]] = [
        {
            'role': 'system',
            'content': build_system_prompt(
                upload_infos=upload_infos,
                enable_vectorization=enable_vectorization,
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
            messages.append({'role': 'user', 'content': msg.content})
        elif msg.message_type == ChatMessage.MESSAGE_TYPE_ASSISTANT:
            messages.append({'role': 'assistant', 'content': msg.content})

    user_parts: List[str] = []
    if uploaded_file_context:
        user_parts.append(uploaded_file_context)
    if rag_context:
        user_parts.append(
            f'[ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n{rag_context}\n[/ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n\n'
            'Используй эту информацию, чтобы подсказать пользователю по интерфейсу и возможностям сайта. '
            'Если релевантного контекста нет — так и скажи, не выдумывай разделы и кнопки.'
        )
    user_parts.append(message)
    messages.append({'role': 'user', 'content': '\n\n'.join(user_parts)})

    return messages, rag_chunks
