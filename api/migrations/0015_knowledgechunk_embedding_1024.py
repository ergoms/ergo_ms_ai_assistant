from django.db import migrations
import pgvector.django

EMBEDDING_DIMENSIONS = 1024


def _reset_embeddings(apps, schema_editor):
    KnowledgeChunk = apps.get_model('ai_assistant', 'KnowledgeChunk')
    KnowledgeDocument = apps.get_model('ai_assistant', 'KnowledgeDocument')
    KnowledgeChunk.objects.all().delete()
    updates = {'is_indexed': False}
    field_names = {field.name for field in KnowledgeDocument._meta.fields}
    if 'indexing_status' in field_names:
        updates['indexing_status'] = 'pending'
    if 'indexed_at' in field_names:
        updates['indexed_at'] = None
    if 'indexing_error' in field_names:
        updates['indexing_error'] = ''
    KnowledgeDocument.objects.update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0014_user_public_id'),
    ]

    operations = [
        migrations.RunPython(_reset_embeddings, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='knowledgechunk',
            name='ai_assistan_embed_hnsw_idx',
        ),
        migrations.RemoveField(
            model_name='knowledgechunk',
            name='embedding',
        ),
        migrations.AddField(
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
