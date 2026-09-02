"""
ModuleBridge — публичный API ai_assistant для других модулей.

Операции ai_assistant.* предназначены для потребителей через bridge.call;
внутри модуля предпочтительны прямые сервисы/views.

Chat-профили хостов: bridge.provide_many(CHAT_PROFILES_GROUP, key, {
  id, ask_stream_op, session_module?, mini_chat_module?, order?
}).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from src.core.integrations import bridge
from src.core.integrations.module_contracts import (
    CORE_USER_DELETE,
    MEDIA_UPLOAD_QUOTA_POLICIES_GROUP,
)
from src.core.utils.knowledge_pack import register_module_knowledge_sign_read
from src.core.utils.media_upload_quota import (
    allows_module_permission,
    env_upload_rate,
)

from .chat_profiles import CHAT_PROFILES_GROUP  # noqa: F401 — публичный экспорт константы
from .ownership import owner_public_id
from .permissions import AI_ASSISTANT_VIEW, MODULE_NAME


def _parse_uuid(value: Any) -> Optional[UUID]:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


@bridge.provide_op('ai_assistant.chat.session.get_or_create')
def _chat_session_get_or_create(
    user,
    module: str,
    title: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    from modules.ai_assistant.api.models import ChatSession

    if user is None or not getattr(user, 'is_authenticated', False):
        return None

    if metadata:
        session, _created = ChatSession.objects.get_or_create(
            user_public_id=owner_public_id(user),
            module=module,
            metadata=metadata,
            defaults={'title': title or ''},
        )
    else:
        session = ChatSession.objects.create(
            user_public_id=owner_public_id(user),
            module=module,
            title=title or '',
        )

    return {
        'id': str(session.id),
        'title': session.title,
        'module': session.module,
        'metadata': session.metadata,
    }


@bridge.provide_op('ai_assistant.chat.message.add')
def _chat_message_add(
    session_id,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    user=None,
) -> Optional[Dict[str, Any]]:
    from modules.ai_assistant.api.models import ChatMessage, ChatSession

    if user is None or not getattr(user, 'is_authenticated', False):
        return None

    session_uuid = _parse_uuid(session_id)
    if session_uuid is None:
        return None

    session = ChatSession.objects.filter(
        id=session_uuid,
        user_public_id=owner_public_id(user),
    ).first()
    if session is None:
        return None

    message_type = role if role in ('user', 'assistant') else 'user'
    message = ChatMessage.objects.create(
        session=session,
        message_type=message_type,
        content=content,
        metadata=metadata or {},
    )
    return {
        'id': str(message.id),
        'type': message.message_type,
        'message_type': message.message_type,
        'content': message.content,
    }


@bridge.provide_op('ai_assistant.knowledge.document.create')
def _knowledge_document_create(
    user,
    title: str,
    content: str = '',
    file_type: str = '',
    source: str = '',
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    from modules.ai_assistant.api.models import KnowledgeDocument

    if user is None or not getattr(user, 'is_authenticated', False):
        return None

    doc = KnowledgeDocument.objects.create(
        user_public_id=owner_public_id(user),
        corpus=KnowledgeDocument.CORPUS_USER,
        title=title,
        content=content,
        file_type=file_type,
        source=source,
        metadata=metadata or {},
    )
    return {'id': str(doc.id), 'title': doc.title}


@bridge.provide_op('ai_assistant.knowledge.document.get')
def _knowledge_document_get(user, document_id) -> Optional[Dict[str, Any]]:
    from modules.ai_assistant.api.models import KnowledgeDocument

    doc_uuid = _parse_uuid(document_id)
    if doc_uuid is None or user is None:
        return None
    doc = KnowledgeDocument.objects.filter(
        id=doc_uuid,
        user_public_id=owner_public_id(user),
        corpus=KnowledgeDocument.CORPUS_USER,
    ).first()
    if doc is None:
        return None
    return {'id': str(doc.id), 'title': doc.title, 'metadata': doc.metadata}


@bridge.provide_op('ai_assistant.knowledge.index')
def _knowledge_index(document_id, user) -> Dict[str, Any]:
    from modules.ai_assistant.api.models import KnowledgeDocument
    from modules.ai_assistant.api.rag import RAGIndexingError, RAGIndexingService

    doc_uuid = _parse_uuid(document_id)
    if doc_uuid is None or user is None:
        return {'success': False, 'error': 'Документ не найден'}

    doc = KnowledgeDocument.objects.filter(
        id=doc_uuid,
        user_public_id=owner_public_id(user),
        corpus=KnowledgeDocument.CORPUS_USER,
    ).first()
    if doc is None:
        return {'success': False, 'error': 'Документ не найден'}

    try:
        service = RAGIndexingService()
        result = service.index_document(doc)
        return {'success': True, **result}
    except RAGIndexingError as exc:
        return {'success': False, 'error': str(exc)}


@bridge.provide_op('ai_assistant.knowledge.search')
def _knowledge_search(
    query: str,
    user,
    document_ids: Optional[List[str]] = None,
    top_k: Optional[int] = None,
) -> Dict[str, Any]:
    from modules.ai_assistant.api.rag import RAGRetrievalError, RAGRetrievalService
    from modules.ai_assistant.api.rag.embeddings import OllamaEmbeddingsService
    from modules.ai_assistant.api.settings import (
        OLLAMA_BASE_URL,
        OLLAMA_EMBEDDINGS_MODEL,
        RAG_SIMILARITY_THRESHOLD,
        RAG_TOP_K,
    )

    if user is None:
        return {'success': False, 'chunks': []}

    embeddings = OllamaEmbeddingsService(base_url=OLLAMA_BASE_URL, model=OLLAMA_EMBEDDINGS_MODEL)
    retrieval = RAGRetrievalService(
        embeddings_service=embeddings,
        top_k=top_k or RAG_TOP_K,
        similarity_threshold=RAG_SIMILARITY_THRESHOLD,
    )
    try:
        chunks = retrieval.retrieve_relevant_chunks(
            query=query,
            user=user,
            document_ids=document_ids,
            include_system=True,
        )
        return {'success': True, 'chunks': chunks}
    except RAGRetrievalError as exc:
        return {'success': False, 'error': str(exc), 'chunks': []}


@bridge.provide_op('ai_assistant.document.parse')
def _document_parse(
    file_path: str = '',
    content: str = '',
    user=None,
) -> Dict[str, Any]:
    """Парсинг через media_api path или сырой content. Произвольные FS-пути запрещены."""
    from rest_framework.exceptions import ValidationError

    from src.core.utils.mixins import validate_media_path

    from modules.ai_assistant.api.media_storage import parse_localized_document
    from modules.ai_assistant.api.rag import DocumentParseError

    if user is None or not getattr(user, 'is_authenticated', False):
        return {'success': False, 'error': 'Требуется аутентифицированный пользователь'}

    if content and not file_path:
        return {'success': True, 'content': content, 'file_type': 'txt'}

    if not file_path:
        return {'success': False, 'error': 'Не указан file_path или content'}

    try:
        storage_path = validate_media_path(file_path, 'file_path')
    except ValidationError as exc:
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict):
            err = detail.get('file_path') or next(iter(detail.values()), None)
            return {'success': False, 'error': str(err)}
        return {'success': False, 'error': str(exc)}

    # Только пути модуля ai_assistant (не чужие каталоги media).
    if not str(storage_path).replace('\\', '/').startswith('ai_assistant/'):
        return {'success': False, 'error': 'Путь файла вне хранилища ai_assistant'}

    try:
        text, file_type = parse_localized_document(storage_path)
        return {'success': True, 'content': text, 'file_type': file_type}
    except DocumentParseError as exc:
        return {'success': False, 'error': str(exc)}


bridge.provide_many(MEDIA_UPLOAD_QUOTA_POLICIES_GROUP, 'ai_assistant_rag', {
    'target_dir_prefix': 'ai_assistant/rag_documents',
    'quota': 'ai_assistant_rag',
    'rate': lambda: env_upload_rate('AI_ASSISTANT_UPLOAD_RATE_RAG', '60/minute'),
    'allows': allows_module_permission(MODULE_NAME, AI_ASSISTANT_VIEW),
})

@bridge.subscribe_to(CORE_USER_DELETE)
def _on_user_delete(*, user_public_id=None, **_):
    if not user_public_id:
        return
    from .models import ChatSession, KnowledgeDocument, LlmJob
    LlmJob.objects.filter(user_public_id=user_public_id).delete()
    ChatSession.objects.filter(user_public_id=user_public_id).delete()
    KnowledgeDocument.objects.filter(user_public_id=user_public_id).delete()


bridge.provide_many(MEDIA_UPLOAD_QUOTA_POLICIES_GROUP, 'ai_assistant_chat', {
    'target_dir_prefix': 'ai_assistant/chat_uploads',
    'quota': 'ai_assistant_chat',
    'rate': lambda: env_upload_rate('AI_ASSISTANT_UPLOAD_RATE_CHAT', '20/minute'),
    'allows': allows_module_permission(MODULE_NAME, AI_ASSISTANT_VIEW),
})

register_module_knowledge_sign_read('ai_assistant')
