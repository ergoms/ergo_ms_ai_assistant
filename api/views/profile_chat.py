"""
SSE-прокси чата для внешних chat-профилей.

Сессии хранятся в ai_assistant; генерация ответа — bridge.call(ask_stream_op хоста).
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any

from django.db import close_old_connections
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from src.core.integrations import bridge
from src.core.utils.mixins import SwaggerSafeMixin

from ..chat_profiles import get_server_profile
from ..models import ChatMessage, ChatSession
from ..permissions import CanViewAiAssistant
from .helpers import _safe_json_dumps

logger = logging.getLogger(__name__)

_SSE_KEEPALIVE_SEC = 15.0
_WORKER_QUEUE_TIMEOUT_SEC = 1.0


class ProfileChatStreamView(SwaggerSafeMixin, APIView):
    """
    POST /api/ai_assistant/chat/profiles/<profile_id>/stream/

    Формат SSE как у ChatStreamView: preparing / chunk / done / error.
    """

    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]
    parser_classes = [JSONParser]

    def post(self, request, profile_id: str):
        if self.is_swagger_fake_view():
            return Response({'success': True})

        profile = get_server_profile(profile_id)
        if profile is None:
            return Response(
                {'success': False, 'error': 'Неизвестный chat-профиль'},
                status=status.HTTP_404_NOT_FOUND,
            )

        message = request.data.get('message')
        session_id = request.data.get('session_id')
        module = request.data.get('module') or profile['session_module']
        user = request.user

        if not message or not str(message).strip():
            return Response(
                {'success': False, 'error': 'Не указано сообщение'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = str(message).strip()

        session = None
        if session_id:
            session = ChatSession.objects.filter(id=session_id, user=user).first()

        if session is None:
            session = ChatSession.objects.create(
                user=user,
                module=module,
                title=message[:50],
                metadata={'profile': profile['id']},
            )
        elif not session.metadata:
            session.metadata = {'profile': profile['id']}
            session.save(update_fields=['metadata'])
        elif session.metadata.get('profile') != profile['id']:
            session.metadata['profile'] = profile['id']
            session.save(update_fields=['metadata'])

        ChatMessage.objects.create(
            session=session,
            message_type=ChatMessage.MESSAGE_TYPE_USER,
            content=message,
            metadata={'profile': profile['id']},
        )

        history = list(
            ChatMessage.objects.filter(session=session)
            .order_by('created_at')
            .values('message_type', 'content')
        )
        # Последнее user-сообщение уже в history; ask получит полный контекст без дубля текущего.
        history_payload = [
            {
                'role': 'assistant' if row['message_type'] == ChatMessage.MESSAGE_TYPE_ASSISTANT else 'user',
                'content': row['content'],
            }
            for row in history[:-1]
        ]

        event_queue: queue.Queue = queue.Queue(maxsize=256)

        def emit(event: dict[str, Any]) -> None:
            try:
                event_queue.put_nowait(('event', event))
            except queue.Full:
                pass

        def run_generation() -> None:
            close_old_connections()
            chunk_parts: list[str] = []
            request_started_at = timezone.now()
            assistant_saved = False
            sources: list = []

            try:
                emit({'type': 'preparing', 'session_id': str(session.id)})

                def stream_callback(text: str) -> None:
                    if not text:
                        return
                    chunk_parts.append(text)
                    emit({'type': 'chunk', 'text': text})

                result = bridge.call(
                    profile['ask_stream_op'],
                    user=user,
                    message=message,
                    session_id=str(session.id),
                    history=history_payload,
                    stream_callback=stream_callback,
                    default=None,
                )

                if not isinstance(result, dict) or not result.get('success'):
                    err = (
                        (result or {}).get('error')
                        if isinstance(result, dict)
                        else 'Провайдер профиля недоступен'
                    )
                    emit({'type': 'error', 'message': str(err or 'Ошибка генерации')})
                    return

                full_response = str(result.get('response') or ''.join(chunk_parts))
                if not chunk_parts and full_response:
                    # Хост ответил без стриминга — отдаём одним chunk.
                    emit({'type': 'chunk', 'text': full_response})
                sources = result.get('sources') or []
                if not isinstance(sources, list):
                    sources = []

                response_received_at = timezone.now()
                processing_ms = int(
                    (response_received_at - request_started_at).total_seconds() * 1000
                )
                meta = {
                    'profile': profile['id'],
                    'sources': sources,
                }
                assistant = ChatMessage.objects.create(
                    session=session,
                    message_type=ChatMessage.MESSAGE_TYPE_ASSISTANT,
                    content=full_response,
                    request_started_at=request_started_at,
                    response_received_at=response_received_at,
                    processing_time_ms=processing_ms,
                    metadata=meta,
                )
                assistant_saved = True
                session.updated_at = timezone.now()
                session.save(update_fields=['updated_at'])

                emit({
                    'type': 'done',
                    'full_response': full_response,
                    'session_id': str(session.id),
                    'message_id': str(assistant.id),
                    'processing_time_ms': processing_ms,
                    'timestamp': response_received_at.isoformat(),
                    'sources': sources,
                })
            except Exception as exc:
                logger.exception('Profile chat stream failed profile=%s', profile['id'])
                if not assistant_saved and chunk_parts:
                    try:
                        ChatMessage.objects.create(
                            session=session,
                            message_type=ChatMessage.MESSAGE_TYPE_ASSISTANT,
                            content=''.join(chunk_parts),
                            metadata={
                                'profile': profile['id'],
                                'error': str(exc),
                            },
                        )
                    except Exception:
                        logger.exception('Failed to persist partial profile reply')
                emit({'type': 'error', 'message': str(exc)})
            finally:
                try:
                    event_queue.put_nowait(('end', None))
                except queue.Full:
                    pass
                close_old_connections()

        worker = threading.Thread(target=run_generation, daemon=True)
        worker.start()

        def event_stream():
            yield f"data: {_safe_json_dumps({'type': 'preparing', 'session_id': str(session.id)})}\n\n"
            while True:
                try:
                    kind, payload = event_queue.get(timeout=_WORKER_QUEUE_TIMEOUT_SEC)
                except queue.Empty:
                    if not worker.is_alive():
                        break
                    yield ': keepalive\n\n'
                    continue
                if kind == 'end':
                    break
                if kind == 'event' and payload:
                    # preparing уже отправили синхронно
                    if payload.get('type') == 'preparing':
                        continue
                    yield f'data: {_safe_json_dumps(payload)}\n\n'

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
