from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ai_assistant', '0008_alter_chatsession_help_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgedocument',
            name='corpus',
            field=models.CharField(
                choices=[('user', 'Пользовательский'), ('system', 'Системный')],
                db_index=True,
                default='user',
                help_text='Корпус: пользовательский или системный (документация ERGO MS)',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='knowledgedocument',
            name='user',
            field=models.ForeignKey(
                blank=True,
                help_text='Владелец документа; пусто для системного корпуса',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='knowledge_documents',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name='knowledgedocument',
            index=models.Index(
                fields=['corpus', 'is_indexed'],
                name='ai_assistan_corpus_7f2a1b_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='knowledgedocument',
            index=models.Index(
                fields=['corpus', 'source'],
                name='ai_assistan_corpus_3c9e4d_idx',
            ),
        ),
    ]
