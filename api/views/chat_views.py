import json
import logging
import threading
from queue import Empty, Queue

from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..json_utils import safe_json_dumps
from ..services import chat as chat_service

logger = logging.getLogger(__name__)


class ChatView(APIView):
    """
    POST /api/ai_assistant/chat/
    Простой RAG чат для общих вопросов (без streaming)
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        message = request.data.get("message")
        ollama_config = chat_service.parse_ollama_config(request.data.get("ollama_config"))
        session_id = request.data.get("session_id")
        module = request.data.get("module", "chat")
        uploaded_files = chat_service.collect_uploaded_files(request)
        enable_vectorization = chat_service.parse_enable_vectorization(
            request.data.get("enable_vectorization", False)
        )

        if not message or not message.strip():
            return Response(
                {"success": False, "error": "Не указано сообщение"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document_id = request.data.get("document_id")
            session = chat_service.load_or_create_session(
                request.user, session_id, module, document_id, message
            )
            chat_service.save_user_message(session, message, ollama_config)

            request_started_at = timezone.now()
            runtime_config, client = chat_service.create_client(ollama_config)
            temperature = (ollama_config or {}).get("temperature", 0)

            uploaded_file_context, vector_ids = chat_service.process_uploads_and_file_context(
                session, request.user, uploaded_files, enable_vectorization, ollama_config
            )
            rag_context, _ = chat_service.build_rag_blocks(
                message,
                request.user,
                module,
                session,
                request.data,
                enable_vectorization,
                vector_ids,
                ollama_config,
            )

            messages = chat_service.assemble_chat_messages(
                session,
                message,
                uploaded_files,
                enable_vectorization,
                uploaded_file_context,
                rag_context,
            )

            answer = client.chat(messages, temperature=temperature, stream=False).strip()

            answer, skill_result, skill_display_name, skill_call = chat_service.apply_skills_to_answer(
                answer, message, request.user, session, module
            )

            response_received_at = timezone.now()
            processing_time = int((response_received_at - request_started_at).total_seconds() * 1000)

            message_metadata = chat_service.build_assistant_metadata(
                runtime_config,
                ollama_config,
                skill_display_name,
                skill_call,
                skill_result,
            )

            assistant_message = chat_service.save_assistant_message(
                session,
                answer,
                request_started_at,
                processing_time,
                message_metadata,
            )

            response_data = {
                "success": True,
                "response": answer,
                "message": answer,
                "session_id": str(session.id),
                "message_id": str(assistant_message.id),
                "processing_time_ms": processing_time,
                "timestamp": assistant_message.created_at.isoformat(),
                "skill_name": skill_display_name,
                "skill_call": skill_call,
            }
            if "chart_config" in message_metadata:
                response_data["chart_config"] = message_metadata["chart_config"]

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChatStreamView(APIView):
    """
    POST /api/ai_assistant/chat/stream/
    RAG чат с SSE.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        message = request.data.get("message")
        ollama_config = chat_service.parse_ollama_config(request.data.get("ollama_config"))
        session_id = request.data.get("session_id")
        module = request.data.get("module", "chat")
        uploaded_files = chat_service.collect_uploaded_files(request)
        enable_vectorization = chat_service.parse_enable_vectorization(
            request.data.get("enable_vectorization", False)
        )

        if not message or not message.strip():
            return Response(
                {"success": False, "error": "Не указано сообщение"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document_id = request.data.get("document_id")
        session = chat_service.load_or_create_session(
            request.user, session_id, module, document_id, message
        )
        chat_service.save_user_message(session, message, ollama_config)

        def event_stream():
            try:
                request_started_at = timezone.now()
                runtime_config, client = chat_service.create_client(ollama_config)
                temperature = (ollama_config or {}).get("temperature", 0)

                uploaded_file_context, vector_ids = chat_service.process_uploads_and_file_context(
                    session, request.user, uploaded_files, enable_vectorization, ollama_config
                )
                rag_context, _ = chat_service.build_rag_blocks(
                    message,
                    request.user,
                    module,
                    session,
                    request.data,
                    enable_vectorization,
                    vector_ids,
                    ollama_config,
                )

                messages = chat_service.assemble_chat_messages(
                    session,
                    message,
                    uploaded_files,
                    enable_vectorization,
                    uploaded_file_context,
                    rag_context,
                )

                streaming_chunks_queue: Queue = Queue()
                result_container: dict = {}
                exception_container: dict = {}

                def stream_callback(text):
                    streaming_chunks_queue.put(text)

                def run_chat():
                    try:
                        result = client.chat(
                            messages,
                            temperature=temperature,
                            stream=True,
                            stream_callback=stream_callback,
                        )
                        result_container["response"] = result.strip()
                    except Exception as e:
                        exception_container["error"] = e
                    finally:
                        streaming_chunks_queue.put(None)

                chat_thread = threading.Thread(target=run_chat)
                chat_thread.start()

                while chat_thread.is_alive() or not streaming_chunks_queue.empty():
                    try:
                        chunk = streaming_chunks_queue.get(timeout=0.1)
                        if chunk is None:
                            break
                        yield f"data: {safe_json_dumps({'type': 'chunk', 'text': chunk}, ensure_ascii=False)}\n\n"
                    except Empty:
                        continue

                chat_thread.join(timeout=5.0)

                if "error" in exception_container:
                    raise exception_container["error"]

                response_received_at = timezone.now()
                raw_response = result_container.get("response", "")

                full_response, skill_result, skill_display_name, skill_call = (
                    chat_service.apply_skills_to_answer(
                        raw_response, message, request.user, session, module
                    )
                )

                processing_time = int((response_received_at - request_started_at).total_seconds() * 1000)

                message_metadata = chat_service.build_assistant_metadata(
                    runtime_config,
                    ollama_config,
                    skill_display_name,
                    skill_call,
                    skill_result,
                )

                assistant_message = chat_service.save_assistant_message(
                    session,
                    full_response,
                    request_started_at,
                    processing_time,
                    message_metadata,
                )

                done_event = {
                    "type": "done",
                    "full_response": full_response,
                    "session_id": str(session.id),
                    "message_id": str(assistant_message.id),
                    "processing_time_ms": processing_time,
                    "timestamp": assistant_message.created_at.isoformat(),
                    "skill_name": skill_display_name,
                    "skill_call": skill_call,
                }
                if "chart_config" in message_metadata:
                    done_event["chart_config"] = message_metadata["chart_config"]

                yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
