"""
ModuleBridge — публичный API ai_assistant для других модулей.

Операции ai_assistant.* предназначены для потребителей через bridge.call;
внутри модуля предпочтительны прямые сервисы/views.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from src.core.integrations import bridge


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
            user=user,
            module=module,
            metadata=metadata,
            defaults={'title': title or ''},
        )
    else:
        session = ChatSession.objects.create(user=user, module=module, title=title or '')

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

    session_uuid = _parse_uuid(session_id)
    if session_uuid is None:
        return None

    qs = ChatSession.objects.filter(id=session_uuid)
    if user is not None:
        qs = qs.filter(user=user)
    session = qs.first()
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
        user=user,
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
    doc = KnowledgeDocument.objects.filter(id=doc_uuid, user=user).first()
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

    doc = KnowledgeDocument.objects.filter(id=doc_uuid, user=user).first()
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
        )
        return {'success': True, 'chunks': chunks}
    except RAGRetrievalError as exc:
        return {'success': False, 'error': str(exc), 'chunks': []}


@bridge.provide_op('ai_assistant.document.parse')
def _document_parse(file_path: str = '', content: str = '') -> Dict[str, Any]:
    from modules.ai_assistant.api.rag import DocumentParserService, DocumentParseError

    parser = DocumentParserService()
    try:
        if file_path:
            parsed = parser.parse_file(file_path)
        elif content:
            parsed = {'content': content, 'file_type': 'txt'}
        else:
            return {'success': False, 'error': 'Не указан file_path или content'}
        return {'success': True, **parsed}
    except DocumentParseError as exc:
        return {'success': False, 'error': str(exc)}
