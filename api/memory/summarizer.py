"""
Суммаризация разговора со скользящим окном.
При превышении SUMMARY_TRIGGER_MESSAGES старых сообщений — суммаризируем и помечаем.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """Summarize the following conversation briefly.
Include key facts, user preferences, decisions, and context that would be useful for future messages.
Write in Russian, 3-5 sentences maximum.

Conversation:
{messages_text}

Summary:"""


class ConversationSummarizer:
    """Суммаризатор истории разговора."""

    def __init__(self, llm_client: Any, trigger_count: int = 20):
        self.llm_client = llm_client
        self.trigger_count = trigger_count

    def should_summarize(self, session) -> bool:
        """Проверяет, нужна ли суммаризация для сессии."""
        from ..models import ChatMessage
        unsummarized_count = session.messages.filter(is_summarized=False).count()
        return unsummarized_count >= self.trigger_count

    def summarize_if_needed(self, session) -> Optional[str]:
        """
        Суммаризирует старые сообщения если их набралось достаточно.
        Помечает суммаризированные сообщения. Возвращает текст summary или None.
        """
        from ..models import ChatMessage
        if not self.should_summarize(session):
            return None

        # Берём все несуммаризированные сообщения кроме последних 5
        messages_qs = session.messages.filter(
            is_summarized=False
        ).order_by('created_at')

        total = messages_qs.count()
        # Оставляем последние 5 несуммаризированными
        to_summarize = list(messages_qs[: max(0, total - 5)])

        if not to_summarize:
            return None

        messages_text = "\n".join([
            f"{'Пользователь' if m.message_type == 'user' else 'Ассистент'}: {m.content[:500]}"
            for m in to_summarize
        ])

        try:
            prompt_messages = [
                {"role": "user", "content": SUMMARIZE_PROMPT.format(messages_text=messages_text)}
            ]
            summary_text = self.llm_client.chat(prompt_messages, temperature=0.3, num_predict=400)
            summary_text = summary_text.strip()

            # Обновляем summary сессии (аппендим к существующему)
            existing = session.summary or ""
            if existing:
                new_summary = f"{existing}\n\n[Обновление {len(to_summarize)} сообщений]: {summary_text}"
            else:
                new_summary = summary_text

            session.summary = new_summary
            session.save(update_fields=["summary"])

            # Помечаем суммаризированные сообщения
            ids = [m.id for m in to_summarize]
            ChatMessage.objects.filter(id__in=ids).update(is_summarized=True)

            logger.info(f"Суммаризировано {len(to_summarize)} сообщений для сессии {session.id}")
            return summary_text

        except Exception as e:
            logger.warning(f"Ошибка суммаризации для сессии {session.id}: {e}")
            return None
