"""ergoms api ensure_pgvector — проверка расширения pgvector в БД."""

from django.core.management.base import BaseCommand, CommandError

from modules.ai_assistant.api.rag.pgvector_ops import ensure_pgvector_extension, pgvector_extension_installed


class Command(BaseCommand):
    help = 'Проверяет и при необходимости создаёт расширение pgvector в PostgreSQL'

    def handle(self, *args, **options):
        if pgvector_extension_installed():
            self.stdout.write(self.style.SUCCESS('Расширение pgvector доступно'))
            return
        try:
            ensure_pgvector_extension()
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS('Расширение pgvector создано'))
