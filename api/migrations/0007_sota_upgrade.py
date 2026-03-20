"""
SOTA-апгрейд ai_assistant:
- UserMemory model
- ChatSession.summary
- ChatMessage.is_summarized, feedback
- KnowledgeChunk.parent_chunk
"""
import django.contrib.postgres.fields
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0006_remove_technologicalprocessdocument_state"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # UserMemory model
        migrations.CreateModel(
            name="UserMemory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("content", models.TextField(help_text="Содержимое воспоминания")),
                ("memory_type", models.CharField(
                    choices=[("preference", "Предпочтение"), ("fact", "Факт"), ("context", "Контекст")],
                    default="fact", max_length=20
                )),
                ("embedding", django.contrib.postgres.fields.ArrayField(
                    base_field=models.FloatField(), blank=True, null=True, size=None,
                    help_text="Векторное представление для семантического поиска"
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ai_memories",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AddIndex(
            model_name="usermemory",
            index=models.Index(fields=["user", "-updated_at"], name="ai_asst_usermem_user_idx"),
        ),
        # ChatSession.summary
        migrations.AddField(
            model_name="chatsession",
            name="summary",
            field=models.TextField(blank=True, default="", help_text="Суммаризация старых сообщений сессии"),
        ),
        # ChatMessage.is_summarized
        migrations.AddField(
            model_name="chatmessage",
            name="is_summarized",
            field=models.BooleanField(default=False, help_text="Включено ли это сообщение в summary сессии"),
        ),
        # ChatMessage.feedback
        migrations.AddField(
            model_name="chatmessage",
            name="feedback",
            field=models.SmallIntegerField(
                blank=True, null=True,
                choices=[(-1, "bad"), (1, "good")],
                help_text="Оценка ответа пользователем: 1=хорошо, -1=плохо"
            ),
        ),
        # KnowledgeChunk.parent_chunk
        migrations.AddField(
            model_name="knowledgechunk",
            name="parent_chunk",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="child_chunks",
                to="ai_assistant.knowledgechunk",
                help_text="Родительский chunk для parent-document retrieval"
            ),
        ),
    ]
