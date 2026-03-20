"""
Долгосрочная семантическая память пользователя.
Извлекает факты о пользователе из сообщений и хранит с embeddings для семантического поиска.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

EXTRACT_MEMORY_PROMPT = """Analyze this conversation and extract important facts about the user.
Focus on: role/profession, preferences, technical level, goals, context about their work.
Return a JSON array of strings (facts in Russian). Return empty array [] if no new facts found.
Keep each fact concise (1 sentence).

Conversation:
{messages_text}

Return ONLY valid JSON array, e.g.: ["Пользователь является аналитиком данных", "Предпочитает краткие ответы"]
"""


class UserMemoryService:
    """Сервис долгосрочной памяти пользователя."""

    def __init__(self, llm_client: Any, embeddings_service: Optional[Any] = None):
        self.llm_client = llm_client
        self.embeddings_service = embeddings_service

    def extract_and_save_memories(self, user, messages: list) -> int:
        """
        Извлекает факты из последних сообщений и сохраняет в UserMemory.
        Возвращает количество сохранённых воспоминаний.
        """
        from ..models import UserMemory

        if not messages:
            return 0

        messages_text = "\n".join([
            f"{'Пользователь' if m.get('role') == 'user' else 'Ассистент'}: {str(m.get('content', ''))[:300]}"
            for m in messages[-6:]  # анализируем последние 6 сообщений
        ])

        try:
            prompt_messages = [
                {"role": "user", "content": EXTRACT_MEMORY_PROMPT.format(messages_text=messages_text)}
            ]
            response = self.llm_client.chat(
                prompt_messages, temperature=0.1, format="json", num_predict=300
            )
            facts = json.loads(response.strip())
            if not isinstance(facts, list):
                return 0
        except Exception as e:
            logger.debug(f"Ошибка извлечения воспоминаний: {e}")
            return 0

        saved = 0
        for fact in facts[:5]:  # не более 5 фактов за раз
            fact = str(fact).strip()
            if not fact or len(fact) < 10:
                continue

            # Проверяем дубликаты (упрощённо — по тексту)
            exists = UserMemory.objects.filter(user=user, content=fact).exists()
            if exists:
                continue

            embedding = None
            if self.embeddings_service:
                try:
                    embedding = self.embeddings_service.generate_embedding(fact)
                except Exception:
                    pass

            UserMemory.objects.create(
                user=user,
                content=fact,
                memory_type='fact',
                embedding=embedding,
            )
            saved += 1

        if saved:
            logger.info(f"Сохранено {saved} воспоминаний для пользователя {user}")
        return saved

    def get_relevant_memories(self, user, query: str, top_k: int = 3) -> List[str]:
        """
        Возвращает top_k наиболее релевантных воспоминаний для запроса.
        Использует семантический поиск если доступны embeddings, иначе — последние по времени.
        """
        from ..models import UserMemory

        memories_qs = UserMemory.objects.filter(user=user).order_by('-updated_at')

        if not self.embeddings_service:
            return [m.content for m in memories_qs[:top_k]]

        memories = list(memories_qs)
        if not memories:
            return []

        # Семантический поиск
        try:
            query_embedding = self.embeddings_service.generate_embedding(query)
            scored = []
            for m in memories:
                if m.embedding:
                    sim = _cosine_similarity(query_embedding, m.embedding)
                    scored.append((sim, m.content))
                else:
                    scored.append((0.0, m.content))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [content for _, content in scored[:top_k]]
        except Exception as e:
            logger.debug(f"Ошибка семантического поиска воспоминаний: {e}")
            return [m.content for m in memories[:top_k]]


def _cosine_similarity(vec1: list, vec2: list) -> float:
    if len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    m1 = math.sqrt(sum(a * a for a in vec1))
    m2 = math.sqrt(sum(a * a for a in vec2))
    if m1 == 0 or m2 == 0:
        return 0.0
    return dot / (m1 * m2)
