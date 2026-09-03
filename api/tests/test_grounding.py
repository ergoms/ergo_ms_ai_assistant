from unittest.mock import patch

from django.test import SimpleTestCase

from modules.ai_assistant.api.safety.grounding import (
    extract_ui_claims,
    filter_ungrounded_ui,
    grounding_refusal_text,
    knowledge_text_from_messages,
    ungrounded_ui_claims,
)
from modules.ai_assistant.api.safety.policy import filter_assistant_answer


class GroundingTests(SimpleTestCase):
    def test_extract_quoted_button(self):
        claims = extract_ui_claims('Нажмите кнопку «Создать анализ» в списке.')
        self.assertTrue(any('создать анализ' in item.casefold() for item in claims))

    def test_known_label_is_grounded(self):
        context = '# Создание анализа\nКнопки: Создать анализ, Отмена\n'
        missing = ungrounded_ui_claims('Нажмите «Создать анализ».', context)
        self.assertEqual(missing, [])

    def test_invented_label_is_ungrounded(self):
        context = '# Создание анализа\nКнопки: Создать анализ, Отмена\n'
        missing = ungrounded_ui_claims('Нажмите кнопку «Экспорт в Excel».', context)
        self.assertTrue(missing)

    def test_filter_replaces_ungrounded_answer(self):
        context = 'Кнопки: Сохранить, Отмена'
        text, blocked = filter_ungrounded_ui(
            'Нажмите «Выгрузить архив».',
            knowledge_context=context,
            ui_language='ru',
        )
        self.assertTrue(blocked)
        self.assertEqual(text, grounding_refusal_text('ru'))

    def test_filter_keeps_grounded_answer(self):
        context = 'Кнопки: Сохранить, Отмена'
        answer = 'Нажмите «Сохранить».'
        text, blocked = filter_ungrounded_ui(
            answer,
            knowledge_context=context,
            ui_language='ru',
        )
        self.assertFalse(blocked)
        self.assertEqual(text, answer)

    def test_messages_collect_system_and_rag(self):
        text = knowledge_text_from_messages([
            {'role': 'system', 'content': '[ВОЗМОЖНОСТИ СИСТЕМЫ]\nменю\n'},
            {
                'role': 'user',
                'content': (
                    '[ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\nполе Имя\n'
                    '[/ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n\nгде имя?'
                ),
            },
            {'role': 'user', 'content': 'просто вопрос без справки'},
        ])
        self.assertIn('ВОЗМОЖНОСТИ СИСТЕМЫ', text)
        self.assertIn('поле Имя', text)
        self.assertNotIn('просто вопрос', text)

    def test_policy_uses_grounding(self):
        with patch(
            'modules.ai_assistant.api.safety.policy.assistant_is_admin',
            return_value=False,
        ):
            text, blocked = filter_assistant_answer(
                answer='Нажмите кнопку «Секретный экспорт».',
                user=object(),
                ui_language='ru',
                knowledge_context='Кнопки: Сохранить',
            )
        self.assertTrue(blocked)
        self.assertEqual(text, grounding_refusal_text('ru'))
