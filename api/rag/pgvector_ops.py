"""
Проверка наличия расширения pgvector в PostgreSQL.

Тип vector должен жить в схеме core: Django не включает public в search_path.
"""

from __future__ import annotations

from django.db import connection

from src.core.utils.database.module_schema import CORE_SCHEMA


def _vector_extension_schema() -> str | None:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT n.nspname FROM pg_extension e '
            'JOIN pg_namespace n ON n.oid = e.extnamespace '
            'WHERE e.extname = %s LIMIT 1',
            ['vector'],
        )
        row = cursor.fetchone()
    return row[0] if row else None


def pgvector_extension_installed() -> bool:
    return _vector_extension_schema() == CORE_SCHEMA


def ensure_pgvector_extension() -> None:
    from django.db.utils import OperationalError, ProgrammingError

    if pgvector_extension_installed():
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {CORE_SCHEMA}')
            cursor.execute(
                'SELECT n.nspname FROM pg_extension e '
                'JOIN pg_namespace n ON n.oid = e.extnamespace '
                'WHERE e.extname = %s LIMIT 1',
                ['vector'],
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(f'CREATE EXTENSION vector SCHEMA {CORE_SCHEMA}')
            elif row[0] != CORE_SCHEMA:
                cursor.execute(f'ALTER EXTENSION vector SET SCHEMA {CORE_SCHEMA}')
    except (OperationalError, ProgrammingError) as exc:
        raise RuntimeError(
            'Расширение pgvector не установлено в PostgreSQL. '
            'Для portable: ergoms ai_assistant:install-pgvector. '
            'Для внешней БД: выполните CREATE EXTENSION vector SCHEMA core '
            'от суперпользователя.'
        ) from exc
