"""Адаптер chunking через chonkie (RecursiveChunker / TableChunker + OverlapRefinery)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TABLE_FILE_TYPES = frozenset({'csv', 'xlsx', 'xls'})


def _chunk_text_attr(chunk: Any) -> str:
    text = getattr(chunk, 'text', None)
    if text is None:
        text = getattr(chunk, 'content', None)
    return (text or '').strip()


def _map_chunks(chunks: List[Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        content = _chunk_text_attr(chunk)
        if not content:
            continue
        start = getattr(chunk, 'start_index', None)
        end = getattr(chunk, 'end_index', None)
        result.append({
            'content': content,
            'start_char': start,
            'end_char': end,
            'chunk_index': index,
        })
    return result


def _apply_overlap(chunks: List[Any], chunk_overlap: int) -> List[Any]:
    if chunk_overlap <= 0 or len(chunks) < 2:
        return chunks
    try:
        from chonkie.refinery import OverlapRefinery

        refinery = OverlapRefinery(context_size=chunk_overlap, method='suffix')
        refined = refinery(chunks)
        return list(refined) if refined is not None else chunks
    except Exception as exc:
        logger.warning('OverlapRefinery недоступен, продолжаем без overlap: %s', exc)
        return chunks


def split_text_with_chonkie(
    text: str,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    file_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Разбивает текст на chunks через chonkie.

    chunk_size — в единицах tokenizer='character' (совместимо с прежним символьным размером).
    Для csv/xlsx/xls предпочитает TableChunker, иначе RecursiveChunker.
    """
    if not text or not text.strip():
        return []

    size = max(1, int(chunk_size))
    overlap = max(0, int(chunk_overlap))
    use_table = (file_type or '').lower() in TABLE_FILE_TYPES

    try:
        if use_table:
            from chonkie import TableChunker

            chunker = TableChunker(tokenizer='character', chunk_size=size)
            try:
                chunks = list(chunker(text))
            except Exception as exc:
                logger.warning(
                    'TableChunker не справился (%s), fallback на RecursiveChunker',
                    exc,
                )
                use_table = False

        if not use_table:
            from chonkie import RecursiveChunker

            chunker = RecursiveChunker(tokenizer='character', chunk_size=size)
            chunks = list(chunker(text))

        chunks = _apply_overlap(chunks, overlap)
        mapped = _map_chunks(chunks)
        if mapped:
            return mapped
        logger.warning('chonkie вернул пустые chunks, документ возможно пуст')
        return []
    except ImportError as exc:
        raise RuntimeError(
            'Библиотека chonkie не установлена. Выполните: ergoms python-install'
        ) from exc
    except Exception as exc:
        logger.error('Ошибка chunking через chonkie: %s', exc, exc_info=True)
        raise
