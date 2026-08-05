"""
Проверка наличия расширения pgvector в PostgreSQL.
"""

from __future__ import annotations

from django.db import connection


def pgvector_extension_installed() -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_extension WHERE extname = %s LIMIT 1",
            ['vector'],
        )
        return cursor.fetchone() is not None


def ensure_pgvector_extension() -> None:
    if pgvector_extension_installed():
        return
    from django.db.utils import OperationalError, ProgrammingError

    try:
        with connection.cursor() as cursor:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
    except (OperationalError, ProgrammingError) as exc:
        raise RuntimeError(
            'Расширение pgvector не установлено в PostgreSQL. '
            'Для portable: ergoms ai_assistant:install-pgvector. '
            'Для внешней БД: выполните CREATE EXTENSION vector от суперпользователя.'
        ) from exc
