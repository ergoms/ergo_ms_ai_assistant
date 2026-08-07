import json
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from ..permissions import CanViewAiAssistant
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.http import StreamingHttpResponse
from django.utils import timezone

from src.core.utils.mixins import SwaggerSafeMixin

from ..ollama_gateway import chat_stream, resolved_model
from ..models import ChatSession, ChatMessage
from ..skills.integration import execute_skill_from_llm_response
from ..file_uploads import collect_chat_upload_infos
from ..rag import build_ollama_messages, resolve_ui_language
from .helpers import _get_rag_context, _safe_json_dumps, _get_rag_services

logger = logging.getLogger(__name__)


class ChatStreamView(SwaggerSafeMixin, APIView):
    """
    POST /api/ai_assistant/chat/stream/
    RAG-чат с SSE streaming (LLM в процессе API; параллелизм — семафор gateway).
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
                session = ChatSession.objects.get(id=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                session = None
        else:
            session = None

        document_id = request.data.get('document_id')

        if not session:
            session_metadata = {}
            if document_id:
                session_metadata['document_id'] = document_id
            session = ChatSession.objects.create(
                user=request.user,
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

        def event_stream():
            chunk_parts: list[str] = []
            request_started_at = None
            model_name = None
            assistant_saved = False

            def save_assistant_message(full_response, *, message_metadata, processing_time, response_received_at):
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
                yield f"data: {_safe_json_dumps({'type': 'preparing', 'session_id': str(session.id)}, ensure_ascii=False)}\n\n"

                request_started_at = timezone.now()

                model_name = resolved_model(ollama_config)
                temperature = (ollama_config or {}).get('temperature', 0)

                ui_language = resolve_ui_language(
                    user=request.user,
                    request=request,
                    override=request.data.get('ui_language'),
                )

                messages, _rag_chunks, attachments_meta = build_ollama_messages(
                    message=message,
                    user=request.user,
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
                    yield f"data: {_safe_json_dumps({'type': 'chunk', 'text': chunk}, ensure_ascii=False)}\n\n"

                response_received_at = timezone.now()
                raw_response = ''.join(chunk_parts).strip()

                skill_result, cleaned_response, skill_display_name, skill_call = execute_skill_from_llm_response(
                    raw_response,
                    message,
                    context={'user': request.user, 'session': session, 'module': module}
                )

                if skill_result and skill_result.success:
                    if cleaned_response:
                        full_response = f"{skill_result.result}\n\n{cleaned_response}"
                    else:
                        full_response = str(skill_result.result)
                elif skill_result and not skill_result.success:
                    full_response = (
                        f"{cleaned_response if cleaned_response else raw_response}\n\n"
                        f"Ошибка выполнения навыка: {skill_result.error}"
                    )
                else:
                    full_response = cleaned_response if cleaned_response else raw_response

                processing_time = int((response_received_at - request_started_at).total_seconds() * 1000)

                message_metadata = {
                    'model': model_name,
                    'skill_name': skill_display_name,
                    'skill_call': skill_call,
                }
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

                yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

            except GeneratorExit:
                logger.info('Клиент отключился от chat/stream, session=%s', session.id)
                raise
            except Exception as e:
                logger.error('Ошибка chat/stream: %s', e, exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                if not assistant_saved and chunk_parts:
                    try:
                        raw_response = ''.join(chunk_parts).strip()
                        if raw_response:
                            response_received_at = timezone.now()
                            processing_time = 0
                            if request_started_at is not None:
                                processing_time = int(
                                    (response_received_at - request_started_at).total_seconds() * 1000
                                )
                            meta = {'model': model_name, 'partial_due_to_disconnect': True}
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
                            'Не удалось сохранить ответ chat/stream после отключения клиента, session=%s',
                            session.id,
                        )

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
