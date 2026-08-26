import uuid

from django.conf import settings
from django.db import migrations, models


def _copy_user_public_id(apps, schema_editor):
    ChatSession = apps.get_model('ai_assistant', 'ChatSession')
    KnowledgeDocument = apps.get_model('ai_assistant', 'KnowledgeDocument')
    LlmJob = apps.get_model('ai_assistant', 'LlmJob')
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    id_to_pid = dict(User.objects.all().values_list('pk', 'public_id'))
    for Model, required in (
        (ChatSession, True),
        (LlmJob, True),
        (KnowledgeDocument, False),
    ):
        for row in Model.objects.all().iterator():
            uid = row.user_id
            pid = id_to_pid.get(uid) if uid else None
            if pid is None and required:
                pid = uuid.uuid4()
            row.user_public_id = pid
            row.save(update_fields=['user_public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0013_rename_menu_ai_assistant'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='chatsession',
            name='user_public_id',
            field=models.UUIDField(db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='user_public_id',
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='llmjob',
            name='user_public_id',
            field=models.UUIDField(db_index=True, null=True),
        ),
        migrations.RunPython(_copy_user_public_id, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='chatsession',
            name='ai_assistan_user_id_5ad16b_idx',
        ),
        migrations.RemoveIndex(
            model_name='chatsession',
            name='ai_assistan_user_id_555b0e_idx',
        ),
        migrations.RemoveIndex(
            model_name='knowledgedocument',
            name='ai_assistan_user_id_985efb_idx',
        ),
        migrations.RemoveIndex(
            model_name='llmjob',
            name='ai_assistan_user_id_1c5a3c_idx',
        ),
        migrations.RemoveField(
            model_name='chatsession',
            name='user',
        ),
        migrations.RemoveField(
            model_name='knowledgedocument',
            name='user',
        ),
        migrations.RemoveField(
            model_name='llmjob',
            name='user',
        ),
        migrations.AlterField(
            model_name='chatsession',
            name='user_public_id',
            field=models.UUIDField(db_index=True),
        ),
        migrations.AlterField(
            model_name='llmjob',
            name='user_public_id',
            field=models.UUIDField(db_index=True),
        ),
        migrations.AlterField(
            model_name='knowledgedocument',
            name='user_public_id',
            field=models.UUIDField(
                blank=True,
                db_index=True,
                help_text='Владелец документа; пусто для системного корпуса',
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name='chatsession',
            index=models.Index(fields=['user_public_id', '-updated_at'], name='ai_assistan_usrpid_upd_idx'),
        ),
        migrations.AddIndex(
            model_name='chatsession',
            index=models.Index(
                fields=['user_public_id', 'module', '-updated_at'],
                name='ai_assistan_usrpid_mod_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='knowledgedocument',
            index=models.Index(fields=['user_public_id', '-created_at'], name='ai_assistan_usrpid_crt_idx'),
        ),
        migrations.AddIndex(
            model_name='llmjob',
            index=models.Index(fields=['user_public_id', '-created_at'], name='ai_assistan_usrpid_job_idx'),
        ),
    ]
