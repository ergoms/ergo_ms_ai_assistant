from django.test import SimpleTestCase

from modules.ai_assistant.api.rag.audience import (
    AUDIENCE_ADMIN,
    AUDIENCE_USER,
    audience_for_source,
    normalize_audience,
)


class AudienceForSourceTests(SimpleTestCase):
    def test_admin_guides(self):
        self.assertEqual(
            audience_for_source('user_guides/core/admin_panel_overview.md'),
            AUDIENCE_ADMIN,
        )
        self.assertEqual(
            audience_for_source('user_guides/core/users_roles_access.md'),
            AUDIENCE_ADMIN,
        )


    def test_core_pack_admin_guides(self):
        self.assertEqual(
            audience_for_source('knowledge/core/user_guide:admin_panel_overview'),
            AUDIENCE_ADMIN,
        )
        self.assertEqual(
            audience_for_source('knowledge/core/user_guide:getting_started'),
            AUDIENCE_USER,
        )

    def test_user_guides(self):
        self.assertEqual(
            audience_for_source('user_guides/core/getting_started.md'),
            AUDIENCE_USER,
        )
        self.assertEqual(
            audience_for_source('user_guides/core/profile_and_settings.md'),
            AUDIENCE_USER,
        )

    def test_menu_and_modules_are_admin(self):
        self.assertEqual(audience_for_source('user_ui/site_menu.md'), AUDIENCE_ADMIN)
        self.assertEqual(
            audience_for_source('user_ui/installed_modules.md'),
            AUDIENCE_ADMIN,
        )

    def test_pack_audience_override(self):
        self.assertEqual(
            audience_for_source('knowledge/core/doc-1', pack_audience='admin'),
            AUDIENCE_ADMIN,
        )
        self.assertEqual(
            audience_for_source('knowledge/core/doc-1', pack_audience='end_user'),
            AUDIENCE_USER,
        )

    def test_normalize_legacy_end_user(self):
        self.assertEqual(normalize_audience('end_user'), AUDIENCE_USER)
        self.assertEqual(normalize_audience('admin'), AUDIENCE_ADMIN)
