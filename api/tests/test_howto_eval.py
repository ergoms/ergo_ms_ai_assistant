from django.test import SimpleTestCase

from modules.ai_assistant.api.rag.eval import EVAL_CASES, run_howto_eval
from modules.ai_assistant.api.rag.eval.metrics import score_case
from modules.ai_assistant.api.rag.eval.run import lexical_retrieve


class HowtoEvalRetrieveTests(SimpleTestCase):
    def test_cases_have_ids(self):
        self.assertTrue(EVAL_CASES)
        ids = [case['id'] for case in EVAL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_lexical_prefers_matching_screen(self):
        docs = [
            {'id': 'ui_catalog:Other', 'title': 'Другое', 'text': 'кнопка Выход'},
            {
                'id': 'ui_catalog:PorosityAnalysisList',
                'title': 'Анализ пористости',
                'text': 'Поля:\n- Название анализа\nКнопки: Создать анализ',
            },
        ]
        found = lexical_retrieve('создать анализ пористости', docs, top_k=1)
        self.assertEqual(found[0]['id'], 'ui_catalog:PorosityAnalysisList')

    def test_score_retrieve_uses_catalog_text(self):
        case = {
            'id': 'demo',
            'expected_source_any': ['ui_catalog:DemoCreate'],
            'must_include_any': ['название записи'],
            'forbid': ['manage.py'],
        }
        docs = [{
            'id': 'ui_catalog:DemoCreate',
            'title': 'Создание записи',
            'text': 'Поля:\n- Название записи — обязательно',
        }]
        row = score_case(case, docs, '', retrieve_ok=True)
        self.assertTrue(row['source_hit'])
        self.assertTrue(row['must_include_hit'])
        self.assertTrue(row['forbid_pass'])

    def test_run_retrieve_only_passes(self):
        report = run_howto_eval(ask_llm=False)
        self.assertFalse(report['ask_llm'])
        self.assertTrue(report['cases'])
        for row in report['cases']:
            self.assertTrue(row['retrieve_ok'], row)
            self.assertTrue(row['source_hit'], row)
            self.assertTrue(row['must_include_hit'], row)
            self.assertTrue(row['forbid_pass'], row)
