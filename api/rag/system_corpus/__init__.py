"""Системный корпус знаний ERGO MS для RAG (пользовательский функционал)."""

from .sources import iter_system_corpus_documents
from .sync import sync_system_corpus

__all__ = [
    'iter_system_corpus_documents',
    'sync_system_corpus',
]
