"""Метрики howto-eval: источники, must_include, forbid."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


def _term_aliases(term: str) -> list[str]:
    return [part.strip().lower() for part in (term or '').split('|') if part.strip()]


def contains_term(text: str, term: str) -> bool:
    hay = (text or '').lower()
    return any(alias in hay for alias in _term_aliases(term))


def contains_any(text: str, needles: Sequence[str]) -> bool:
    return any(contains_term(text, needle) for needle in needles if needle)


def contains_all(text: str, needles: Sequence[str]) -> bool:
    required = [needle for needle in needles if needle]
    return bool(required) and all(contains_term(text, needle) for needle in required)


def forbids_ok(text: str, forbidden: Sequence[str]) -> bool:
    hay = (text or '').lower()
    return not any(item.lower() in hay for item in forbidden if item)


def source_blob(documents: Sequence[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for item in documents:
        parts.append(str(item.get('id') or ''))
        parts.append(str(item.get('title') or ''))
        parts.append(str(item.get('text') or ''))
        parts.append(str(item.get('source') or ''))
    return '\n'.join(parts)


def score_case(
    case: Mapping[str, Any],
    documents: Sequence[Mapping[str, Any]],
    response: str = '',
    *,
    retrieve_ok: bool = True,
) -> dict[str, Any]:
    blob = source_blob(documents)
    expected = list(case.get('expected_source_any') or [])
    source_hit = contains_any(blob, expected) if expected else bool(documents)
    answer = (response or '').strip()
    has_response = bool(answer)
    must_any = list(case.get('must_include_any') or [])
    must_all = list(case.get('must_include_all') or [])
    forbid = list(case.get('forbid') or [])
    target = answer if has_response else blob
    hit_any = contains_any(target, must_any) if must_any else True
    hit_all = contains_all(target, must_all) if must_all else True
    must_hit = hit_any and hit_all
    if has_response and not must_any and not must_all:
        must_hit = False
    return {
        'id': case.get('id') or '',
        'retrieve_ok': bool(retrieve_ok) and bool(documents),
        'has_response': has_response,
        'source_hit': source_hit,
        'must_include_hit': must_hit,
        'forbid_pass': forbids_ok(target, forbid),
        'doc_ids': [str(item.get('id') or '') for item in documents],
    }


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)


def aggregate_scores(rows: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    scored = list(rows)
    return {
        'cases': len(scored),
        'source_hit_rate': _mean(1.0 if row.get('source_hit') else 0.0 for row in scored),
        'must_include_rate': _mean(
            1.0 if row.get('must_include_hit') else 0.0 for row in scored
        ),
        'forbid_pass_rate': _mean(1.0 if row.get('forbid_pass') else 0.0 for row in scored),
        'retrieve_ok_rate': _mean(1.0 if row.get('retrieve_ok') else 0.0 for row in scored),
    }
