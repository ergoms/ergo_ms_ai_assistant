"""
Выравнивает схему KnowledgeDocument.corpus, если миграция 0009
отмечена/не отмечена, а колонки/индексы расходятся с моделью.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Проверить и при необходимости создать колонку corpus у KnowledgeDocument'

    def handle(self, *args, **options):
        vendor = connection.vendor
        with connection.cursor() as cursor:
            if vendor == 'postgresql':
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'ai_assistant_knowledgedocument'
                    ORDER BY ordinal_position
                    """
                )
                columns = {row[0] for row in cursor.fetchall()}
                self.stdout.write(f'Колонки: {sorted(columns)}')

                if 'corpus' not in columns:
                    cursor.execute(
                        """
                        ALTER TABLE ai_assistant_knowledgedocument
                        ADD COLUMN corpus varchar(20) DEFAULT 'user' NOT NULL
                        """
                    )
                    cursor.execute(
                        """
                        ALTER TABLE ai_assistant_knowledgedocument
                        ALTER COLUMN corpus DROP DEFAULT
                        """
                    )
                    self.stdout.write(self.style.SUCCESS('Добавлена колонка corpus'))
                else:
                    self.stdout.write('Колонка corpus уже есть')

                # user_id nullable
                cursor.execute(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'ai_assistant_knowledgedocument'
                      AND column_name = 'user_id'
                    """
                )
                row = cursor.fetchone()
                if row and row[0] == 'NO':
                    cursor.execute(
                        """
                        ALTER TABLE ai_assistant_knowledgedocument
                        ALTER COLUMN user_id DROP NOT NULL
                        """
                    )
                    self.stdout.write(self.style.SUCCESS('user_id сделан nullable'))

                for index_name, index_sql in (
                    (
                        'ai_assistan_corpus_7f2a1b_idx',
                        'CREATE INDEX IF NOT EXISTS ai_assistan_corpus_7f2a1b_idx '
                        'ON ai_assistant_knowledgedocument (corpus, is_indexed)',
                    ),
                    (
                        'ai_assistan_corpus_3c9e4d_idx',
                        'CREATE INDEX IF NOT EXISTS ai_assistan_corpus_3c9e4d_idx '
                        'ON ai_assistant_knowledgedocument (corpus, source)',
                    ),
                ):
                    cursor.execute(index_sql)
                    self.stdout.write(f'Индекс {index_name}: OK')

            elif vendor == 'sqlite':
                cursor.execute('PRAGMA table_info(ai_assistant_knowledgedocument)')
                columns = {row[1] for row in cursor.fetchall()}
                self.stdout.write(f'Колонки: {sorted(columns)}')
                if 'corpus' not in columns:
                    cursor.execute(
                        "ALTER TABLE ai_assistant_knowledgedocument "
                        "ADD COLUMN corpus varchar(20) NOT NULL DEFAULT 'user'"
                    )
                    self.stdout.write(self.style.SUCCESS('Добавлена колонка corpus'))
                else:
                    self.stdout.write('Колонка corpus уже есть')
            else:
                self.stderr.write(f'Неподдерживаемый backend: {vendor}')
                return

        self.stdout.write(self.style.SUCCESS('Схема KnowledgeDocument выровнена'))
