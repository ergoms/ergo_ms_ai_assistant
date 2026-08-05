# -*- coding: utf-8 -*-
"""Корневой пункт AI Hub — в секцию «Модули» (order >= 20)."""

from django.db import migrations


def move_menu_to_modules_section(apps, schema_editor):
    from src.core.cms.adp.menu.migration_utils import align_module_root_menu_orders

    align_module_root_menu_orders(apps, 'modules/ai_assistant')


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0009_knowledgedocument_corpus_system'),
        ('cms_adp', '0054_menu_catalog_layout'),
    ]

    operations = [
        migrations.RunPython(move_menu_to_modules_section, migrations.RunPython.noop),
    ]
