import logging

from rest_framework.response import Response
from rest_framework import permissions, status
from ..permissions import CanViewAiAssistant
from rest_framework.viewsets import ViewSet

from src.core.utils.mixins import SwaggerSafeMixin
from ..models import ChatSession

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
        queryset = ChatSession.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        # Фильтрация по модулю
        module = request.query_params.get('module')
        if module:
            queryset = queryset.filter(module=module)
        
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
        queryset = ChatSession.objects.filter(user=user)
        queryset = self.get_safe_queryset(queryset)
        
        try:
            session = queryset.get(id=pk)
        except ChatSession.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Сессия не найдена'
            }, status=status.HTTP_404_NOT_FOUND)
        
        messages = []
        for msg in session.messages.all():
            messages.append({
                'id': str(msg.id),
                'type': msg.message_type,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
                'request_started_at': msg.request_started_at.isoformat() if msg.request_started_at else None,
                'response_received_at': msg.response_received_at.isoformat() if msg.response_received_at else None,
                'processing_time_ms': msg.processing_time_ms,
                'metadata': msg.metadata,
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
            user=user,
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
        queryset = ChatSession.objects.filter(user=user)
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

