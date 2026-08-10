# -*- coding: utf-8 -*-
"""Запасное имя пункта меню: AI Hub → AI ассистент (подпись UI — из titleKey)."""

from django.db import migrations


def rename_menu_label(apps, schema_editor):
    from src.core.cms.adp.menu.migration_utils import MenuMigrationHelper

    helper = MenuMigrationHelper(apps, 'modules/ai_assistant')
    helper.create_group('AI ассистент', 'AIAssistantHub', icon='Bot')


def reverse_rename_menu_label(apps, schema_editor):
    from src.core.cms.adp.menu.migration_utils import MenuMigrationHelper

    helper = MenuMigrationHelper(apps, 'modules/ai_assistant')
    helper.create_group('AI Hub', 'AIAssistantHub', icon='Bot')


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0012_llm_job_events'),
        ('cms_adp', '0054_menu_catalog_layout'),
    ]

    operations = [
        migrations.RunPython(rename_menu_label, reverse_rename_menu_label),
    ]
