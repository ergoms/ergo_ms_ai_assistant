import json
import logging
import queue
import threading
from typing import Any

from django.db import close_old_connections
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from src.core.utils.mixins import SwaggerSafeMixin

from ..file_uploads import collect_chat_upload_infos
from ..models import ChatMessage, ChatSession
from ..ownership import owner_public_id
from ..ollama_gateway import chat_stream, resolved_model
from ..permissions import CanViewAiAssistant
from ..rag import build_ollama_messages, resolve_ui_language
from ..safety.policy import evaluate_user_message, filter_assistant_answer
from ..skills.integration import execute_skill_from_llm_response
from .helpers import _get_rag_context, _get_rag_services, _safe_json_dumps

logger = logging.getLogger(__name__)

# Keepalive SSE, пока RAG/LLM ещё не отдали chunk (иначе прокси/клиент могут рвать тишину).
_SSE_KEEPALIVE_SEC = 15.0
_WORKER_QUEUE_TIMEOUT_SEC = 1.0


class ChatStreamView(SwaggerSafeMixin, APIView):
    """
    POST /api/ai_assistant/chat/stream/
    RAG-чат с SSE. Генерация в фоне потока: обрыв клиента (nginx 499) не убивает LLM —
    ответ сохраняется в сессию, клиент дотягивает через pending recovery.
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        if self.is_swagger_fake_view():
            return Response({'success': True})

        message = request.data.get('message')
        ollama_config = request.data.get('ollama_config')
        session_id = request.data.get('session_id')
        module = request.data.get('module', 'chat')
        upload_infos = collect_chat_upload_infos(request)
        document_id = request.data.get('document_id')
        ui_language_override = request.data.get('ui_language')
        user = request.user

        enable_vectorization = request.data.get('enable_vectorization', False)
        if isinstance(enable_vectorization, str):
            enable_vectorization = enable_vectorization.lower() in ('true', '1', 'yes')

        if isinstance(ollama_config, str):
            try:
                ollama_config = json.loads(ollama_config)
            except (json.JSONDecodeError, TypeError):
                ollama_config = None

        if not message or not message.strip():
            return Response({
                'success': False,
                'error': 'Не указано сообщение'
            }, status=status.HTTP_400_BAD_REQUEST)

        if session_id:
            try:
                session = ChatSession.objects.get(
                    id=session_id,
                    user_public_id=owner_public_id(user),
                )
            except ChatSession.DoesNotExist:
                session = None
        else:
            session = None

        if not session:
            session_metadata = {}
            if document_id:
                session_metadata['document_id'] = document_id
            session = ChatSession.objects.create(
                user_public_id=owner_public_id(user),
                module=module,
                title=message[:50] if message else 'Новый чат',
                metadata=session_metadata
            )
        else:
            if document_id:
                if not session.metadata:
                    session.metadata = {}
                session.metadata['document_id'] = document_id
                session.save(update_fields=['metadata'])

        user_meta: dict = {}
        if ollama_config:
            user_meta['ollama_config'] = ollama_config
        user_message = ChatMessage.objects.create(
            session=session,
            message_type=ChatMessage.MESSAGE_TYPE_USER,
            content=message,
            metadata=user_meta,
        )

        ui_language = resolve_ui_language(
            user=user,
            request=None,
            override=ui_language_override,
        )
        refusal = evaluate_user_message(
            message=message,
            user=user,
            ui_language=ui_language,
            session=session,
            exclude_message_id=user_message.id,
        )
        if refusal:
            request_started_at = timezone.now()
            assistant_message = ChatMessage.objects.create(
                session=session,
                message_type=ChatMessage.MESSAGE_TYPE_ASSISTANT,
                content=refusal,
                request_started_at=request_started_at,
                response_received_at=request_started_at,
                processing_time_ms=0,
                metadata={'safety': 'input_blocked'},
            )
            session.updated_at = timezone.now()
            session.save(update_fields=['updated_at'])

            def blocked_event_stream():
                yield f'data: {_safe_json_dumps({"type": "preparing", "session_id": str(session.id)}, ensure_ascii=False)}\n\n'
                yield f'data: {_safe_json_dumps({"type": "done", "full_response": refusal, "session_id": str(session.id), "message_id": str(assistant_message.id), "processing_time_ms": 0, "timestamp": assistant_message.created_at.isoformat(), "skill_name": None, "skill_call": None}, ensure_ascii=False)}\n\n'

            response = StreamingHttpResponse(
                blocked_event_stream(),
                content_type='text/event-stream',
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response

        # Ограниченная очередь: при обрыве клиента чанки не копятся в RAM.
        event_queue: queue.Queue = queue.Queue(maxsize=256)

        def emit(event: dict[str, Any]) -> None:
            try:
                event_queue.put_nowait(('event', event))
            except queue.Full:
                pass

        def run_generation() -> None:
            close_old_connections()
            chunk_parts: list[str] = []
            request_started_at = None
            model_name = None
            assistant_saved = False

            def save_assistant_message(
                full_response,
                *,
                message_metadata,
                processing_time,
                response_received_at,
            ):
                nonlocal assistant_saved
                assistant_message = ChatMessage.objects.create(
                    session=session,
                    message_type=ChatMessage.MESSAGE_TYPE_ASSISTANT,
                    content=full_response,
                    request_started_at=request_started_at,
                    response_received_at=response_received_at,
                    processing_time_ms=processing_time,
                    metadata=message_metadata,
                )
                session.updated_at = timezone.now()
                session.save(update_fields=['updated_at'])
                assistant_saved = True
                return assistant_message

            try:
                emit({'type': 'preparing', 'session_id': str(session.id)})

                request_started_at = timezone.now()
                model_name = resolved_model(ollama_config)
                temperature = (ollama_config or {}).get('temperature', 0)

                messages, _rag_chunks, attachments_meta = build_ollama_messages(
                    message=message,
                    user=user,
                    session=session,
                    module=module,
                    upload_infos=upload_infos,
                    enable_vectorization=enable_vectorization,
                    ollama_config=ollama_config,
                    request_document_id=document_id,
                    get_rag_services=_get_rag_services,
                    get_rag_context=_get_rag_context,
                    exclude_message_id=user_message.id,
                    ui_language=ui_language,
                )
                if attachments_meta:
                    meta = dict(user_message.metadata or {})
                    meta['attachments'] = attachments_meta
                    user_message.metadata = meta
                    user_message.save(update_fields=['metadata'])

                for chunk in chat_stream(
                    messages,
                    ollama_config=ollama_config,
                    temperature=temperature,
                ):
                    chunk_parts.append(chunk)
                    emit({'type': 'chunk', 'text': chunk})

                response_received_at = timezone.now()
                raw_response = ''.join(chunk_parts).strip()

                raw_response, output_blocked = filter_assistant_answer(
                    answer=raw_response,
                    user=user,
                    ui_language=ui_language,
                )
                if output_blocked:
                    emit({'type': 'replace', 'text': raw_response})
                    skill_result = None
                    cleaned_response = raw_response
                    skill_display_name = None
                    skill_call = None
                else:
                    skill_result, cleaned_response, skill_display_name, skill_call = (
                        execute_skill_from_llm_response(
                            raw_response,
                            message,
                            context={'user': user, 'session': session, 'module': module},
                        )
                    )

                if skill_result and skill_result.success:
                    if cleaned_response:
                        full_response = f'{skill_result.result}\n\n{cleaned_response}'
                    else:
                        full_response = str(skill_result.result)
                elif skill_result and not skill_result.success:
                    full_response = (
                        f'{cleaned_response if cleaned_response else raw_response}\n\n'
                        f'Ошибка выполнения навыка: {skill_result.error}'
                    )
                else:
                    full_response = cleaned_response if cleaned_response else raw_response

                processing_time = int(
                    (response_received_at - request_started_at).total_seconds() * 1000
                )

                message_metadata = {
                    'model': model_name,
                    'skill_name': skill_display_name,
                    'skill_call': skill_call,
                }
                if output_blocked:
                    message_metadata['safety'] = 'output_blocked'
                if ollama_config:
                    message_metadata['ollama_config'] = ollama_config

                if skill_result and skill_result.success and skill_result.metadata:
                    if 'chart_config' in skill_result.metadata:
                        message_metadata['chart_config'] = skill_result.metadata['chart_config']

                assistant_message = save_assistant_message(
                    full_response,
                    message_metadata=message_metadata,
                    processing_time=processing_time,
                    response_received_at=response_received_at,
                )

                done_event = {
                    'type': 'done',
                    'full_response': full_response,
                    'session_id': str(session.id),
                    'message_id': str(assistant_message.id),
                    'processing_time_ms': processing_time,
                    'timestamp': assistant_message.created_at.isoformat(),
                    'skill_name': skill_display_name,
                    'skill_call': skill_call,
                }
                if 'chart_config' in message_metadata:
                    done_event['chart_config'] = message_metadata['chart_config']
                emit(done_event)
            except Exception as exc:
                logger.error('Ошибка chat/stream: %s', exc, exc_info=True)
                if not assistant_saved and chunk_parts:
                    try:
                        raw_response = ''.join(chunk_parts).strip()
                        if raw_response:
                            response_received_at = timezone.now()
                            processing_time = 0
                            if request_started_at is not None:
                                processing_time = int(
                                    (response_received_at - request_started_at).total_seconds()
                                    * 1000
                                )
                            meta = {
                                'model': model_name,
                                'partial_due_to_error': True,
                            }
                            if ollama_config:
                                meta['ollama_config'] = ollama_config
                            save_assistant_message(
                                raw_response,
                                message_metadata=meta,
                                processing_time=processing_time,
                                response_received_at=response_received_at,
                            )
                    except Exception:
                        logger.exception(
                            'Не удалось сохранить частичный ответ chat/stream, session=%s',
                            session.id,
                        )
                emit({'type': 'error', 'message': str(exc)})
            finally:
                try:
                    event_queue.put_nowait(('stop', None))
                except queue.Full:
                    try:
                        event_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        event_queue.put_nowait(('stop', None))
                    except queue.Full:
                        pass
                close_old_connections()

        worker = threading.Thread(
            target=run_generation,
            name=f'ai-chat-stream-{session.id}',
            daemon=True,
        )
        worker.start()

        def event_stream():
            idle_since = timezone.now()
            while True:
                try:
                    kind, payload = event_queue.get(timeout=_WORKER_QUEUE_TIMEOUT_SEC)
                except queue.Empty:
                    if not worker.is_alive() and event_queue.empty():
                        break
                    # SSE comment — не парсится клиентом, держит прокси/соединение живым
                    idle_for = (timezone.now() - idle_since).total_seconds()
                    if idle_for >= _SSE_KEEPALIVE_SEC:
                        yield ': keepalive\n\n'
                        idle_since = timezone.now()
                    continue

                if kind == 'stop':
                    break

                idle_since = timezone.now()
                yield f'data: {_safe_json_dumps(payload, ensure_ascii=False)}\n\n'

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
