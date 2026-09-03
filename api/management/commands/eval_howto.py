from django.core.management.base import BaseCommand, CommandError

from modules.ai_assistant.api.rag.eval import run_howto_eval


class Command(BaseCommand):
    help = 'Прогон золотых вопросов про экраны и поля (каталог UI, без Ollama по умолчанию)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ask',
            action='store_true',
            help='Вызвать живую модель Ollama после лексического поиска',
        )

    def handle(self, *args, **options):
        ask_llm = bool(options.get('ask'))
        report = run_howto_eval(ask_llm=ask_llm)
        metrics = report.get('metrics') or {}
        self.stdout.write(
            'режим={mode}; кейсов={cases}; пропущено={skipped}; '
            'source_hit={hit:.2f}; must_include={must:.2f}; '
            'forbid_pass={forbid:.2f}; retrieve_ok={ok:.2f}'.format(
                mode='ask' if report.get('ask_llm') else 'retrieve',
                cases=metrics.get('cases') or 0,
                skipped=metrics.get('skipped') or 0,
                hit=float(metrics.get('source_hit_rate') or 0),
                must=float(metrics.get('must_include_rate') or 0),
                forbid=float(metrics.get('forbid_pass_rate') or 0),
                ok=float(metrics.get('retrieve_ok_rate') or 0),
            )
        )
        failed = 0
        for row in report.get('cases') or []:
            ok = (
                row.get('source_hit')
                and row.get('must_include_hit')
                and row.get('forbid_pass')
                and row.get('retrieve_ok')
            )
            if not ok:
                failed += 1
            self.stdout.write(
                f'- {row.get("id")}: source={int(bool(row.get("source_hit")))} '
                f'must={int(bool(row.get("must_include_hit")))} '
                f'forbid={int(bool(row.get("forbid_pass")))} '
                f'docs={",".join(row.get("doc_ids") or []) or "—"}'
            )
            preview = (row.get('response') or '').replace('\n', ' ').strip()
            if preview:
                self.stdout.write(f'  {preview[:280]}')
            if row.get('ask_error'):
                self.stdout.write(f'  ошибка модели: {row["ask_error"]}')
        if failed:
            raise CommandError(f'упало кейсов: {failed}')
