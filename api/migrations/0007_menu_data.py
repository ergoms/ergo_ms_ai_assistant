# -*- coding: utf-8 -*-
"""
Миграция данных: регистрация пунктов меню модуля AI Assistant.
"""

from django.db import migrations


def populate_menu(apps, schema_editor):
    from src.core.cms.adp.menu.migration_utils import MenuMigrationHelper

    helper = MenuMigrationHelper(apps, 'modules/ai_assistant')
    helper.clear_module_items()
    helper.create_group('AI Hub', 'AIAssistantHub', icon='Bot')


def reverse_populate_menu(apps, schema_editor):
    from src.core.cms.adp.menu.migration_utils import MenuMigrationHelper

    MenuMigrationHelper(apps, 'modules/ai_assistant').clear_module_items()


class Migration(migrations.Migration):

    dependencies = [
        ('cms_adp', '0001_initial_squashed_0042_drop_graduate_employment_tables'),
        ('ai_assistant', '0006_remove_technologicalprocessdocument_state'),
    ]

    operations = [
        migrations.RunPython(populate_menu, reverse_populate_menu),
    ]
