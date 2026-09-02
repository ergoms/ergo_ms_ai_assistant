import logging

from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.decorators import action
from ..permissions import CanViewAiAssistant
from rest_framework.viewsets import ViewSet

from src.core.utils.mixins import SwaggerSafeMixin
from ..chat_profiles import hub_module_for_mini, is_hub_session_module
from ..models import ChatSession
from ..ownership import owner_public_id

logger = logging.getLogger(__name__)

class ChatSessionViewSet(ViewSet, SwaggerSafeMixin):
    """
    ViewSet для работы с сессиями чатов
    """
    permission_classes = [permissions.IsAuthenticated, CanViewAiAssistant]
    
    def list(self, request):
        """
        GET /api/ai_assistant/chat_sessions/
        Получить список сессий чатов пользователя
        """
        user = self.get_safe_user()
        queryset = ChatSession.objects.filter(
            user_public_id=owner_public_id(user, required=False),
        )
        queryset = self.get_safe_queryset(queryset)
        
        # Фильтрация по модулю. Без фильтра — без мини-чата (он не в списке хаба).
        module = request.query_params.get('module')
        if module:
            queryset = queryset.filter(module=module)
        else:
            queryset = queryset.exclude(module='mini_chat')

        sessions = []
        for session in queryset[:50]:  # Ограничиваем 50 последними
            sessions.append({
                'id': str(session.id),
                'title': session.title or 'Без названия',
                'module': session.module,
                'message_count': session.message_count,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'metadata': session.metadata or {},
            })
        
        return Response({
            'success': True,
            'sessions': sessions,
            'count': len(sessions),
        })
    
    def retrieve(self, request, pk=None):
        """
        GET /api/ai_assistant/chat_sessions/{id}/
        Получить сессию чата с сообщениями
        """
        user = self.get_safe_user()
        queryset = ChatSession.objects.filter(
            user_public_id=owner_public_id(user, required=False),
        )
        queryset = self.get_safe_queryset(queryset)
        
        try:
            session = queryset.get(id=pk)
        except ChatSession.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Сессия не найдена'
            }, status=status.HTTP_404_NOT_FOUND)
        
        from ..media_storage import signed_url

        messages = []
        for msg in session.messages.all():
            metadata = dict(msg.metadata or {})
            attachments = metadata.get('attachments')
            if isinstance(attachments, list):
                enriched = []
                for item in attachments:
                    if not isinstance(item, dict):
                        continue
                    row = dict(item)
                    path = row.get('path') or ''
                    if path and row.get('kind') == 'image':
                        row['signed_url'] = signed_url(path)
                    enriched.append(row)
                metadata['attachments'] = enriched
            messages.append({
                'id': str(msg.id),
                'type': msg.message_type,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
                'request_started_at': msg.request_started_at.isoformat() if msg.request_started_at else None,
                'response_received_at': msg.response_received_at.isoformat() if msg.response_received_at else None,
                'processing_time_ms': msg.processing_time_ms,
                'metadata': metadata,
            })
        
        return Response({
            'success': True,
            'session': {
                'id': str(session.id),
                'title': session.title or 'Без названия',
                'module': session.module,
                'message_count': session.message_count,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'metadata': session.metadata or {},
            },
            'messages': messages,
        })
    
    def create(self, request):
        """
        POST /api/ai_assistant/chat_sessions/
        Создать новую сессию чата
        """
        user = self.get_safe_user()
        if not user:
            return Response({
                'success': False,
                'error': 'Пользователь не найден'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        title = request.data.get('title', 'Новый чат')
        module = request.data.get('module', 'chat')
        
        session = ChatSession.objects.create(
            user_public_id=owner_public_id(user),
            title=title,
            module=module
        )
        return Response({
            'success': True,
            'session': {
                'id': str(session.id),
                'title': session.title,
                'module': session.module,
                'message_count': session.message_count,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
            }
        }, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, pk=None):
        """
        DELETE /api/ai_assistant/chat_sessions/{id}/
        Удалить сессию чата
        """
        user = self.get_safe_user()
        queryset = ChatSession.objects.filter(
            user_public_id=owner_public_id(user, required=False),
        )
        queryset = self.get_safe_queryset(queryset)
        
        try:
            session = queryset.get(id=pk)
            session.delete()
            return Response({
                'success': True,
                'message': 'Сессия удалена'
            }, status=status.HTTP_200_OK)
        except ChatSession.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Сессия не найдена'
            }, status=status.HTTP_404_NOT_FOUND)

    def _owner_sessions(self):
        user = self.get_safe_user()
        queryset = ChatSession.objects.filter(
            user_public_id=owner_public_id(user, required=False),
        )
        return self.get_safe_queryset(queryset)

    def _session_payload(self, session):
        return {
            'id': str(session.id),
            'title': session.title or 'Без названия',
            'module': session.module,
            'message_count': session.message_count,
            'created_at': session.created_at.isoformat(),
            'updated_at': session.updated_at.isoformat(),
            'metadata': session.metadata or {},
        }

    @action(detail=True, methods=['post'], url_path='save')
    def save_to_hub(self, request, pk=None):
        """
        POST /api/ai_assistant/chat_sessions/{id}/save/
        Перенести сессию мини-чата в список хаба (module mini → chat).
        """
        queryset = self._owner_sessions()
        try:
            session = queryset.get(id=pk)
        except ChatSession.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Сессия не найдена',
            }, status=status.HTTP_404_NOT_FOUND)

        if is_hub_session_module(session.module):
            return Response({
                'success': True,
                'already_saved': True,
                'session': self._session_payload(session),
            })

        hub_module = hub_module_for_mini(session.module)
        if not hub_module:
            return Response({
                'success': False,
                'error': 'Эту сессию нельзя сохранить в хаб',
            }, status=status.HTTP_400_BAD_REQUEST)

        session.module = hub_module
        session.save(update_fields=['module', 'updated_at'])
        return Response({
            'success': True,
            'already_saved': False,
            'session': self._session_payload(session),
        })

