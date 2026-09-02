from unittest.mock import patch

from django.test import SimpleTestCase

from modules.ai_assistant.api.rag.prompts import (
    ADMIN_SYSTEM_PROMPT,
    USER_SYSTEM_PROMPT,
    role_system_prompt,
)
from modules.ai_assistant.api.rag.retrieval import RAGRetrievalService
from modules.ai_assistant.api.rag.audience import AUDIENCE_ADMIN


class RolePromptTests(SimpleTestCase):
    def test_user_prompt(self):
        with patch(
            'modules.ai_assistant.api.rag.prompts.assistant_is_admin',
            return_value=False,
        ):
            text = role_system_prompt(user=object())
        self.assertEqual(text, USER_SYSTEM_PROMPT.strip())
        self.assertIn('Не объясняй админ-панель', text)

    def test_admin_prompt(self):
        with patch(
            'modules.ai_assistant.api.rag.prompts.assistant_is_admin',
            return_value=True,
        ):
            text = role_system_prompt(user=object())
        self.assertEqual(text, ADMIN_SYSTEM_PROMPT.strip())
        self.assertIn('админ-панели', text)


class RetrievalAudienceFilterTests(SimpleTestCase):
    def test_non_admin_hides_admin_audience(self):
        service = RAGRetrievalService(embeddings_service=object())
        with patch(
            'modules.ai_assistant.api.rag.retrieval.assistant_is_admin',
            return_value=False,
        ):
            query = service._system_corpus_audience_q(object())
        self.assertIsNotNone(query)
        self.assertIn(AUDIENCE_ADMIN, str(query))

    def test_admin_sees_all_audiences(self):
        service = RAGRetrievalService(embeddings_service=object())
        with patch(
            'modules.ai_assistant.api.rag.retrieval.assistant_is_admin',
            return_value=True,
        ):
            self.assertIsNone(service._system_corpus_audience_q(object()))
