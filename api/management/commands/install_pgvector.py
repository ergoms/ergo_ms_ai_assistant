"""ergoms ai_assistant:install-pgvector — установка pgvector в portable PostgreSQL."""

from django.core.management.base import BaseCommand, CommandError

from ....deployment.install_pgvector import PROJECT_ROOT, install_pgvector


class Command(BaseCommand):
    help = 'Устанавливает расширение pgvector в portable PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Переустановить pgvector, даже если маркер уже есть',
        )

    def handle(self, *args, **options):
        code = install_pgvector(PROJECT_ROOT, force=options.get('force', False))
        if code != 0:
            raise CommandError('Установка pgvector завершилась с ошибкой')
