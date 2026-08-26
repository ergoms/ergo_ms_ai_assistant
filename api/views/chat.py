import json
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from ..permissions import CanViewAiAssistant
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone

from src.core.utils.mixins import SwaggerSafeMixin

from ..ollama_gateway import chat as ollama_chat, resolved_model
from ..models import ChatSession, ChatMessage
from ..ownership import owner_public_id
from ..skills.integration import execute_skill_from_llm_response
from ..file_uploads import collect_chat_upload_infos
from ..rag import build_ollama_messages, resolve_ui_language
from .helpers import _get_rag_context, _get_rag_services

logger = logging.getLogger(__name__)


class ChatView(SwaggerSafeMixin, APIView):
    """
    POST /api/ai_assistant/chat/
    RAG-чат без streaming (LLM в процессе API).
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

        try:
            if session_id:
                try:
                    session = ChatSession.objects.get(
                        id=session_id,
                        user_public_id=owner_public_id(request.user),
                    )
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
                    user_public_id=owner_public_id(request.user),
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

            answer = ollama_chat(
                messages,
                ollama_config=ollama_config,
                temperature=temperature,
                stream=False,
            ).strip()

            skill_result, cleaned_answer, skill_display_name, skill_call = execute_skill_from_llm_response(
                answer,
                message,
                context={'user': request.user, 'session': session, 'module': module}
            )

            if skill_result and skill_result.success:
                if cleaned_answer:
                    answer = f"{skill_result.result}\n\n{cleaned_answer}"
                else:
                    answer = skill_result.result
            elif skill_result and not skill_result.success:
                answer = f"{cleaned_answer}\n\nОшибка выполнения навыка: {skill_result.error}"
            else:
                answer = cleaned_answer if cleaned_answer else answer

            response_received_at = timezone.now()
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

            assistant_message = ChatMessage.objects.create(
                session=session,
                message_type=ChatMessage.MESSAGE_TYPE_ASSISTANT,
                content=answer,
                request_started_at=request_started_at,
                response_received_at=response_received_at,
                processing_time_ms=processing_time,
                metadata=message_metadata
            )

            session.updated_at = timezone.now()
            session.save(update_fields=['updated_at'])

            response_data = {
                'success': True,
                'response': answer,
                'message': answer,
                'session_id': str(session.id),
                'message_id': str(assistant_message.id),
                'processing_time_ms': processing_time,
                'timestamp': assistant_message.created_at.isoformat(),
                'skill_name': skill_display_name,
                'skill_call': skill_call,
            }
            if 'chart_config' in message_metadata:
                response_data['chart_config'] = message_metadata['chart_config']

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error('Ошибка chat: %s', e, exc_info=True)
            return Response({
                'success': False,
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
