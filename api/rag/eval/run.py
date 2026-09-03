"""Прогон howto-eval: лексический поиск по каталогу, опционально LLM."""
from __future__ import annotations

import re
from typing import Any

from src.core.utils.module_registry import get_installed_module_names
from src.core.utils.ui_catalog import collect_core_ui_documents, collect_module_ui_documents

from .cases import EVAL_CASES, HowtoEvalCase
from .metrics import aggregate_scores, score_case

_TOKEN_RE = re.compile(r'[A-Za-zА-Яа-яЁё0-9]{3,}')


def _tokenize(text: str) -> list[str]:
    return [item.casefold() for item in _TOKEN_RE.findall(text or '')]


def collect_eval_documents(*, owners: list[str] | None = None) -> list[dict[str, Any]]:
    documents = list(collect_core_ui_documents())
    names = owners if owners is not None else list(get_installed_module_names())
    for name in names:
        for item in collect_module_ui_documents(name):
            documents.append(item)
    return documents


def lexical_retrieve(
    question: str,
    documents: list[dict[str, Any]],
    *,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    terms = _tokenize(question)
    if not terms:
        return list(documents[:top_k])
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in documents:
        blob = f"{item.get('id') or ''} {item.get('title') or ''} {item.get('text') or ''}"
        hay = blob.casefold()
        score = sum(hay.count(term) for term in terms)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _score, item in scored[:top_k]]


def _case_available(case: HowtoEvalCase, installed: set[str]) -> bool:
    owner = str(case.get('require_owner') or '').strip()
    if not owner:
        return True
    return owner in installed


def _ask_llm(question: str, documents: list[dict[str, Any]]) -> str:
    from modules.ai_assistant.api.ollama_gateway import chat as ollama_chat

    context = '\n\n'.join(
        f"# {item.get('title') or item.get('id')}\n{item.get('text') or ''}"
        for item in documents
    )
    messages = [
        {
            'role': 'system',
            'content': (
                'Отвечай только по справке ниже. Не выдумывай кнопки и поля. '
                'Если в справке нет ответа — так и скажи.'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'[ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n{context}\n[/ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ]\n\n'
                f'{question}'
            ),
        },
    ]
    return str(ollama_chat(messages) or '').strip()


def run_howto_eval(*, ask_llm: bool = False) -> dict[str, Any]:
    installed = set(get_installed_module_names())
    catalog = collect_eval_documents()
    rows: list[dict[str, Any]] = []
    skipped = 0
    for case in EVAL_CASES:
        if not _case_available(case, installed):
            skipped += 1
            continue
        found = lexical_retrieve(case['question'], catalog)
        response = ''
        if ask_llm:
            try:
                response = _ask_llm(case['question'], found)
            except Exception as exc:
                response = ''
                row = score_case(case, found, response, retrieve_ok=bool(found))
                row['ask_error'] = str(exc)
                rows.append(row)
                continue
        row = score_case(case, found, response, retrieve_ok=bool(found))
        if response:
            row['response'] = response
        rows.append(row)
    metrics = aggregate_scores(rows)
    metrics['skipped'] = skipped
    return {
        'ask_llm': ask_llm,
        'cases': rows,
        'metrics': metrics,
    }
