# Generated manually for pgvector migration

from django.db import migrations, models
import pgvector.django

EMBEDDING_DIMENSIONS = 768


def _copy_embeddings_forward(apps, schema_editor):
    KnowledgeChunk = apps.get_model('ai_assistant', 'KnowledgeChunk')
    for chunk in KnowledgeChunk.objects.iterator():
        legacy = chunk.embedding_legacy
        if not legacy:
            continue
        if len(legacy) != EMBEDDING_DIMENSIONS:
            continue
        chunk.embedding_vector = legacy
        chunk.save(update_fields=['embedding_vector'])


def _set_indexing_status_done(apps, schema_editor):
    KnowledgeDocument = apps.get_model('ai_assistant', 'KnowledgeDocument')
    KnowledgeDocument.objects.filter(is_indexed=True).update(indexing_status='done')


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0010_menu_modules_section'),
    ]

    operations = [
        pgvector.django.VectorExtension(),
        migrations.AddField(
            model_name='knowledgedocument',
            name='indexing_error',
            field=models.TextField(blank=True, default='', help_text='Текст ошибки последней индексации'),
        ),
        migrations.AddField(
            model_name='knowledgedocument',
            name='indexing_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Ожидает'),
                    ('running', 'Выполняется'),
                    ('done', 'Готово'),
                    ('failed', 'Ошибка'),
                ],
                db_index=True,
                default='pending',
                help_text='Статус фоновой индексации документа',
                max_length=20,
            ),
        ),
        migrations.RunPython(_set_indexing_status_done, migrations.RunPython.noop),
        migrations.RenameField(
            model_name='knowledgechunk',
            old_name='embedding',
            new_name='embedding_legacy',
        ),
        migrations.AddField(
            model_name='knowledgechunk',
            name='embedding_vector',
            field=pgvector.django.VectorField(
                dimensions=EMBEDDING_DIMENSIONS,
                help_text='Векторное представление текста (embedding) для поиска по схожести',
                null=True,
            ),
        ),
        migrations.RunPython(_copy_embeddings_forward, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='knowledgechunk',
            name='embedding_legacy',
        ),
        migrations.RenameField(
            model_name='knowledgechunk',
            old_name='embedding_vector',
            new_name='embedding',
        ),
        migrations.AlterField(
            model_name='knowledgechunk',
            name='embedding',
            field=pgvector.django.VectorField(
                dimensions=EMBEDDING_DIMENSIONS,
                help_text='Векторное представление текста (embedding) для поиска по схожести',
            ),
        ),
        migrations.AddIndex(
            model_name='knowledgechunk',
            index=pgvector.django.HnswIndex(
                name='ai_assistan_embed_hnsw_idx',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ),
    ]
