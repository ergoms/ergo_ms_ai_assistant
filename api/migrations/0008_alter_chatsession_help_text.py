from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0007_menu_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatsession',
            name='module',
            field=models.CharField(
                default='chat',
                help_text='Модуль AI ассистента (chat, docs, code и т.д.)',
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='chatsession',
            name='metadata',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Дополнительные данные сессии',
            ),
        ),
    ]
