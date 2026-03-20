"""
Общая логика чата: сессия, файлы, RAG, сбор messages для LLM, постобработка навыков.
Поддерживает: smart context window, суммаризация, память пользователя, sources, suggestions.
"""

from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import Any

from django.utils import timezone

from ..assistant_settings import (
    MEMORY_MAX_TOKENS,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    SUGGESTIONS_ENABLED,
    SUMMARY_MAX_TOKENS,
    SUMMARY_TRIGGER_MESSAGES,
)

from ..llm_utils import create_ollama_client
from ..models import ChatMessage, ChatSession, KnowledgeDocument
from ..rag import DocumentParseError, DocumentParserService, RAGIndexingService
from ..rag_service import get_rag_context, get_rag_services  # noqa: F401 (re-exported)
from ..skills.integration import execute_skill_from_llm_response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    """Грубая оценка количества токенов (4 символа ≈ 1 токен)."""
    return max(1, len(text) // 4)


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


# ---------------------------------------------------------------------------
# Сессия
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Файлы и RAG
# ---------------------------------------------------------------------------

def process_uploads_and_file_context(
    session: ChatSession,
    user,
    uploaded_files: list,
    enable_vectorization: bool,
    ollama_config: dict | None,
) -> tuple[str, list[str]]:
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


def build_sources_from_chunks(chunks: list) -> list[dict]:
    """Формирует список источников из найденных RAG chunks для отображения пользователю."""
    seen_docs: dict[str, int] = {}  # doc_id → chunk_counter
    sources = []
    for chunk in chunks[:5]:  # max 5 источников
        doc_id = chunk.get("document_id", "")
        doc_title = chunk.get("document_title", "Документ")
        chunk_index = chunk.get("chunk_index", 0)
        # Превью: первые 150 символов дочернего chunk
        preview = (chunk.get("child_content") or chunk.get("content", ""))[:150]
        if preview and len(preview) == 150:
            preview += "..."

        if doc_id not in seen_docs:
            seen_docs[doc_id] = 0
            sources.append({
                "document_id": doc_id,
                "document_title": doc_title,
                "chunk_index": chunk_index,
                "preview": preview,
                "similarity": round(chunk.get("similarity", 0.0), 3),
            })
    return sources


# ---------------------------------------------------------------------------
# Суммаризация и память
# ---------------------------------------------------------------------------

def run_summarization_if_needed(session: ChatSession, client: Any) -> None:
    """Запускает суммаризацию если накопилось достаточно сообщений."""
    try:
        from ..memory.summarizer import ConversationSummarizer
        summarizer = ConversationSummarizer(llm_client=client, trigger_count=SUMMARY_TRIGGER_MESSAGES)
        summarizer.summarize_if_needed(session)
    except Exception as e:
        logger.warning("Ошибка суммаризации: %s", e)


def get_user_memory_context(user, query: str, client: Any, embeddings_service: Any) -> str:
    """Возвращает строку с релевантными воспоминаниями пользователя."""
    try:
        from ..memory.user_memory import UserMemoryService
        svc = UserMemoryService(llm_client=client, embeddings_service=embeddings_service)
        memories = svc.get_relevant_memories(user, query, top_k=3)
        if memories:
            return "Контекст о пользователе:\n" + "\n".join(f"- {m}" for m in memories)
    except Exception as e:
        logger.debug("Ошибка получения памяти пользователя: %s", e)
    return ""


def save_user_memories_async(user, messages: list, client: Any, embeddings_service: Any) -> None:
    """Фоновое извлечение и сохранение воспоминаний после ответа."""
    try:
        from ..memory.user_memory import UserMemoryService
        svc = UserMemoryService(llm_client=client, embeddings_service=embeddings_service)
        svc.extract_and_save_memories(user, messages)
    except Exception as e:
        logger.debug("Ошибка сохранения памяти пользователя: %s", e)


# ---------------------------------------------------------------------------
# Smart context window management
# ---------------------------------------------------------------------------

def build_system_prompt_parts(uploaded_files: list, enable_vectorization: bool) -> list[str]:
    parts: list[str] = []
    if not uploaded_files:
        return parts
    if enable_vectorization:
        parts.append(
            "Пользователь загрузил файлы, которые были проиндексированы с помощью векторного поиска. "
            "Используй информацию из векторного поиска для точных и релевантных ответов."
        )
    else:
        parts.append(
            "Пользователь загрузил файлы. Используй информацию из загруженных файлов для ответа."
        )
    return parts


def append_history_messages(messages: list[dict], session: ChatSession, max_messages: int = 10) -> None:
    previous_messages = session.messages.order_by("created_at")[:max_messages]
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
    user_memory_context: str = "",
) -> list[dict]:
    """
    Собирает messages для LLM с учётом приоритетов контекста:
    summary (400 tokens) > recent_messages > rag_context > memory (200 tokens).
    """
    messages: list[dict] = []
    system_parts = build_system_prompt_parts(uploaded_files, enable_vectorization)

    # Добавляем summary сессии в system (если есть)
    if session.summary:
        summary_text = session.summary
        # Обрезаем до SUMMARY_MAX_TOKENS
        max_chars = SUMMARY_MAX_TOKENS * 4
        if len(summary_text) > max_chars:
            summary_text = summary_text[-max_chars:]
        system_parts.append(f"[Краткое резюме предыдущего разговора]\n{summary_text}")

    # Добавляем память пользователя в system (если есть)
    if user_memory_context:
        mem_text = user_memory_context
        max_mem_chars = MEMORY_MAX_TOKENS * 4
        if len(mem_text) > max_mem_chars:
            mem_text = mem_text[:max_mem_chars]
        system_parts.append(mem_text)

    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

    append_history_messages(messages, session)
    user_content = compose_user_message_content(message, uploaded_file_context, rag_context)
    messages.append({"role": "user", "content": user_content})
    return messages


# ---------------------------------------------------------------------------
# Навыки
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Suggested questions
# ---------------------------------------------------------------------------

def generate_suggestions(
    client: Any,
    message: str,
    answer: str,
) -> list[str]:
    """Генерирует 3 suggested follow-up вопроса асинхронно."""
    if not SUGGESTIONS_ENABLED:
        return []
    try:
        prompt = (
            f"Based on this Q&A, generate 3 short follow-up questions the user might ask next. "
            f"Return ONLY a JSON array of strings in Russian. "
            f"Question: {message[:200]}\nAnswer: {answer[:300]}\n"
            f'Example: ["Вопрос 1?", "Вопрос 2?", "Вопрос 3?"]'
        )
        msgs = [{"role": "user", "content": prompt}]
        resp = client.chat(msgs, temperature=0.4, format="json", num_predict=200)
        if isinstance(resp, str):
            suggestions = json.loads(resp)
            if isinstance(suggestions, list):
                return [str(s) for s in suggestions[:3] if s]
    except Exception as e:
        logger.debug("Ошибка генерации suggestions: %s", e)
    return []


# ---------------------------------------------------------------------------
# Metadata и сохранение
# ---------------------------------------------------------------------------

def build_assistant_metadata(
    runtime_config,
    ollama_config: dict | None,
    skill_display_name: str | None,
    skill_call: Any,
    skill_result: Any,
    sources: list | None = None,
    suggestions: list | None = None,
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
    if sources:
        metadata["sources"] = sources
    if suggestions:
        metadata["suggestions"] = suggestions
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
