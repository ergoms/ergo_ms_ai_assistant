"""
Общая логика чата: сессия, файлы, RAG, сбор messages для LLM, постобработка навыков.
"""

from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import Any

from django.utils import timezone

from src.config.settings.ai_assistant import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE

from ..llm_utils import create_ollama_client
from ..models import ChatMessage, ChatSession, KnowledgeDocument
from ..rag import DocumentParseError, DocumentParserService, RAGIndexingService
from ..rag_service import get_rag_context, get_rag_services
from ..skills.integration import execute_skill_from_llm_response

logger = logging.getLogger(__name__)


def parse_enable_vectorization(raw: Any) -> bool:
    if isinstance(raw, str):
        return raw.lower() in ("true", "1", "yes")
    return bool(raw)


def parse_ollama_config(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return raw


def collect_uploaded_files(request) -> list:
    uploaded_files = request.FILES.getlist("files")
    if not uploaded_files:
        single_file = request.FILES.get("file")
        if single_file:
            uploaded_files = [single_file]
    return uploaded_files


def load_or_create_session(
    user,
    session_id: str | None,
    module: str,
    document_id: str | None,
    message: str,
) -> ChatSession:
    session = None
    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id, user=user)
        except ChatSession.DoesNotExist:
            session = None

    if not session:
        session_metadata: dict = {}
        if document_id:
            session_metadata["document_id"] = document_id
        return ChatSession.objects.create(
            user=user,
            module=module,
            title=message[:50] if message else "Новый чат",
            metadata=session_metadata,
        )

    if document_id:
        if not session.metadata:
            session.metadata = {}
        session.metadata["document_id"] = document_id
        session.save(update_fields=["metadata"])
    return session


def save_user_message(session: ChatSession, message: str, ollama_config: dict | None) -> ChatMessage:
    return ChatMessage.objects.create(
        session=session,
        message_type=ChatMessage.MESSAGE_TYPE_USER,
        content=message,
        metadata={"ollama_config": ollama_config} if ollama_config else {},
    )


def process_uploads_and_file_context(
    session: ChatSession,
    user,
    uploaded_files: list,
    enable_vectorization: bool,
    ollama_config: dict | None,
) -> tuple[str, list[str]]:
    """
    Векторизация загрузок и/или извлечение текста в контекст.
    Возвращает (uploaded_file_context, vectorized_document_ids для этого запроса).
    """
    uploaded_file_context = ""
    vectorized_document_ids: list[str] = []
    if session.metadata and "vectorized_documents" in session.metadata:
        vectorized_document_ids = list(session.metadata["vectorized_documents"])

    if not uploaded_files:
        return "", vectorized_document_ids

    if enable_vectorization:
        try:
            embeddings_service, _ = get_rag_services(ollama_config)
            indexing_service = RAGIndexingService(
                embeddings_service=embeddings_service,
                chunk_size=RAG_CHUNK_SIZE,
                chunk_overlap=RAG_CHUNK_OVERLAP,
            )
            new_document_ids: list[str] = []
            for uploaded_file in uploaded_files:
                try:
                    temp_doc = KnowledgeDocument.objects.create(
                        user=user,
                        title=f"Временный документ: {uploaded_file.name}",
                        file=uploaded_file,
                        source=f"chat_upload_{session.id}",
                        metadata={
                            "session_id": str(session.id),
                            "is_temporary": True,
                            "uploaded_at": timezone.now().isoformat(),
                        },
                    )
                    indexing_result = indexing_service.index_document(temp_doc, force_reindex=True)
                    if indexing_result.get("success"):
                        new_document_ids.append(str(temp_doc.id))
                        logger.info("Файл %s проиндексирован (ID: %s)", uploaded_file.name, temp_doc.id)
                    else:
                        logger.warning(
                            "Не удалось проиндексировать %s: %s",
                            uploaded_file.name,
                            indexing_result.get("error"),
                        )
                        temp_doc.delete()
                except Exception as e:
                    logger.error("Ошибка векторизации файла %s: %s", uploaded_file.name, e, exc_info=True)

            if new_document_ids:
                if not session.metadata:
                    session.metadata = {}
                if "vectorized_documents" not in session.metadata:
                    session.metadata["vectorized_documents"] = []
                session.metadata["vectorized_documents"].extend(new_document_ids)
                session.save(update_fields=["metadata"])
                vectorized_document_ids = list(session.metadata["vectorized_documents"])
        except Exception as e:
            logger.error("Ошибка при векторизации файлов: %s", e, exc_info=True)
    else:
        file_contexts = []
        for uploaded_file in uploaded_files:
            try:
                file_obj = BytesIO(uploaded_file.read())
                extracted_content, _detected = DocumentParserService.parse_document(
                    file_obj=file_obj,
                    filename=uploaded_file.name,
                )
                if extracted_content:
                    max_len = 2000
                    if len(extracted_content) > max_len:
                        extracted_content = extracted_content[:max_len] + "..."
                    file_contexts.append(
                        f"[СОДЕРЖИМОЕ ФАЙЛА: {uploaded_file.name}]\n{extracted_content}\n[/СОДЕРЖИМОЕ ФАЙЛА]"
                    )
            except DocumentParseError as e:
                logger.warning("Не удалось извлечь текст из %s: %s", uploaded_file.name, e)
            except Exception as e:
                logger.error("Ошибка обработки файла %s: %s", uploaded_file.name, e, exc_info=True)
        if file_contexts:
            uploaded_file_context = (
                "\n\n".join(file_contexts)
                + "\n\nИспользуй информацию из загруженных файлов для ответа на вопрос пользователя."
            )

    return uploaded_file_context, vectorized_document_ids


def build_rag_blocks(
    message: str,
    user,
    module: str,
    session: ChatSession,
    request_data,
    enable_vectorization: bool,
    vectorized_document_ids: list[str],
    ollama_config: dict | None,
) -> tuple[str, list]:
    rag_context = ""
    rag_chunks: list = []
    if enable_vectorization and vectorized_document_ids:
        rag_context, rag_chunks = get_rag_context(
            query=message,
            user=user,
            ollama_config=ollama_config,
            document_ids=vectorized_document_ids,
        )
    elif module == "docs":
        document_id = None
        if session.metadata and "document_id" in session.metadata:
            document_id = session.metadata["document_id"]
        elif request_data.get("document_id"):
            document_id = request_data.get("document_id")
        document_ids = [document_id] if document_id else None
        rag_context, rag_chunks = get_rag_context(
            query=message,
            user=user,
            ollama_config=ollama_config,
            document_ids=document_ids,
        )
    return rag_context, rag_chunks


def build_system_prompt_parts(uploaded_files: list, enable_vectorization: bool) -> list[str]:
    parts: list[str] = []
    if not uploaded_files:
        return parts
    if enable_vectorization:
        parts.append(
            "Пользователь загрузил файлы, которые были проиндексированы с помощью векторного поиска. "
            "Используй информацию из векторного поиска для точных и релевантных ответов. "
            "Учитывай контекст из всех загруженных файлов при ответе на вопросы."
        )
    else:
        parts.append(
            "Пользователь загрузил файлы. Используй информацию из загруженных файлов для ответа на вопросы. "
            "Учитывай содержимое всех загруженных файлов при формировании ответа."
        )
    return parts


def append_history_messages(messages: list[dict], session: ChatSession) -> None:
    previous_messages = session.messages.order_by("created_at")[:10]
    for msg in previous_messages:
        if msg.message_type == ChatMessage.MESSAGE_TYPE_USER:
            messages.append({"role": "user", "content": msg.content})
        elif msg.message_type == ChatMessage.MESSAGE_TYPE_ASSISTANT:
            messages.append({"role": "assistant", "content": msg.content})


def compose_user_message_content(message: str, uploaded_file_context: str, rag_context: str) -> str:
    user_message_parts: list[str] = []
    if uploaded_file_context:
        user_message_parts.append(uploaded_file_context)
    if rag_context:
        user_message_parts.append(
            f"[ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n{rag_context}\n[/ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n\n"
            "Используй эту информацию для ответа на вопрос пользователя. "
            "Если в базе знаний есть релевантная информация, обязательно используй её. "
            "Если информации нет, отвечай на основе своих знаний."
        )
    user_message_parts.append(message)
    return "\n\n".join(user_message_parts)


def assemble_chat_messages(
    session: ChatSession,
    message: str,
    uploaded_files: list,
    enable_vectorization: bool,
    uploaded_file_context: str,
    rag_context: str,
) -> list[dict]:
    """system + история (включая только что сохранённое user-сообщение) + текущий user с контекстами."""
    messages: list[dict] = []
    system_prompt_parts = build_system_prompt_parts(uploaded_files, enable_vectorization)
    if system_prompt_parts:
        messages.append({"role": "system", "content": "\n".join(system_prompt_parts)})
    append_history_messages(messages, session)
    user_content = compose_user_message_content(message, uploaded_file_context, rag_context)
    messages.append({"role": "user", "content": user_content})
    return messages


def apply_skills_to_answer(
    raw_answer: str,
    user_text: str,
    user,
    session: ChatSession,
    module: str,
) -> tuple[str, Any, str | None, Any]:
    skill_result, cleaned_answer, skill_display_name, skill_call = execute_skill_from_llm_response(
        raw_answer,
        user_text,
        context={"user": user, "session": session, "module": module},
    )
    if skill_result and skill_result.success:
        if cleaned_answer:
            answer = f"{skill_result.result}\n\n{cleaned_answer}"
        else:
            answer = str(skill_result.result)
    elif skill_result and not skill_result.success:
        answer = f"{cleaned_answer}\n\n⚠️ Ошибка выполнения навыка: {skill_result.error}"
    else:
        answer = cleaned_answer if cleaned_answer else raw_answer
    return answer, skill_result, skill_display_name, skill_call


def build_assistant_metadata(
    runtime_config,
    ollama_config: dict | None,
    skill_display_name: str | None,
    skill_call: Any,
    skill_result: Any,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "model": runtime_config.model,
        "skill_name": skill_display_name,
        "skill_call": skill_call,
    }
    if ollama_config:
        metadata["ollama_config"] = ollama_config
    if skill_result and skill_result.success and skill_result.metadata:
        if "chart_config" in skill_result.metadata:
            metadata["chart_config"] = skill_result.metadata["chart_config"]
    return metadata


def save_assistant_message(
    session: ChatSession,
    content: str,
    request_started_at,
    processing_time_ms: int,
    message_metadata: dict[str, Any],
) -> ChatMessage:
    assistant_message = ChatMessage.objects.create(
        session=session,
        message_type=ChatMessage.MESSAGE_TYPE_ASSISTANT,
        content=content,
        request_started_at=request_started_at,
        response_received_at=timezone.now(),
        processing_time_ms=processing_time_ms,
        metadata=message_metadata,
    )
    session.updated_at = timezone.now()
    session.save(update_fields=["updated_at"])
    return assistant_message


def create_client(ollama_config: dict | None):
    """Обертка над create_ollama_client для view-слоя."""
    return create_ollama_client(ollama_config)

