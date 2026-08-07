"""
Индексация пользовательского корпуса функционала сайта для RAG ai_assistant.

Использование:
    ergoms api sync_system_knowledge
    ergoms ai_assistant:sync-knowledge
"""
from django.core.management.base import BaseCommand, CommandError

from modules.ai_assistant.api.rag.system_corpus import sync_system_corpus
from modules.ai_assistant.api.settings import RAG_SYSTEM_CORPUS_ENABLED
from modules.ai_assistant.api.views.helpers import _get_rag_services


class Command(BaseCommand):
    help = 'Синхронизировать справку по функционалу сайта в RAG ai_assistant'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Переиндексировать все файлы, даже без изменения content_hash',
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Индексировать синхронно в процессе команды (без Celery)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, что будет обновлено, без записи в БД',
        )

    def handle(self, *args, **options):
        force = options['force']
        dry_run = options['dry_run']

        if not RAG_SYSTEM_CORPUS_ENABLED and not force:
            self.stderr.write(
                self.style.WARNING(
                    'RAG_SYSTEM_CORPUS_ENABLED=false. Передайте --force или включите флаг в .env'
                )
            )
            return

        self.stdout.write('Синхронизация пользовательской справки ERGO MS...')
        if dry_run:
            self.stdout.write('(dry-run — без записи)')

        embeddings_service, _ = _get_rag_services()
        result = sync_system_corpus(
            embeddings_service=embeddings_service,
            force=force,
            dry_run=dry_run,
            use_celery=not options.get('sync', False),
        )

        self.stdout.write(
            f"Документов: {result.get('files', 0)}; "
            f"создано: {result.get('created', 0)}; "
            f"обновлено: {result.get('updated', 0)}; "
            f"пропущено: {result.get('skipped', 0)}; "
            f"проиндексировано: {result.get('indexed', 0)}; "
            f"в очереди: {result.get('queued', 0)}; "
            f"удалено устаревших: {result.get('removed', 0)}"
        )

        errors = result.get('errors') or []
        if errors:
            self.stderr.write(self.style.ERROR(f'Ошибок: {len(errors)}'))
            for item in errors[:20]:
                self.stderr.write(f"  {item.get('source')}: {item.get('error')}")
            if len(errors) > 20:
                self.stderr.write(f'  ... и ещё {len(errors) - 20}')
            raise CommandError(f'Синхронизация корпуса завершилась с ошибками: {len(errors)}')

        if result.get('success'):
            self.stdout.write(self.style.SUCCESS('Пользовательская справка синхронизирована'))
            return

        raise CommandError(result.get('error') or 'Ошибка синхронизации')
