from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from workbench import factories
from workbench.accounts.models import User
from workbench.tools.testing import messages


class AccountsTest(TestCase):
    def test_user(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("", "")

        user = User.objects.create_user("test@example.com", "")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.has_perm("stuff"))
        self.assertTrue(user.has_module_perms("stuff"))
        self.assertFalse(user.is_staff)

    def test_admin(self):
        user = User.objects.create_superuser("test@example.com", "")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.has_perm("stuff"))
        self.assertTrue(user.has_module_perms("stuff"))
        self.assertTrue(user.is_staff)

    def test_choices(self):
        u1 = factories.UserFactory.create(_full_name="M A", is_active=True)
        u2 = factories.UserFactory.create(_full_name="M I", is_active=False)

        self.assertEqual(
            list(User.objects.choices(collapse_inactive=False)),
            [
                ("", "Alle Benutzer"),
                ("Aktiv", [(u1.pk, "M A")]),
                ("Inaktiv", [(u2.pk, "M I")]),
            ],
        )

        self.assertEqual(
            list(User.objects.choices(collapse_inactive=True)),
            [
                ("", "Alle Benutzer"),
                (0, "Inaktive Benutzer"),
                ("Aktiv", [(u1.pk, "M A")]),
            ],
        )

    def test_ordering(self):
        self.assertTrue(User(_short_name="a") < User(_full_name="b"))

    @override_settings(FEATURES={"glassfrog": False})
    def test_feature_required(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get(
            reverse("report_hours_by_circle"), HTTP_REFERER="/test/"
        )
        self.assertRedirects(response, "/test/", fetch_redirect_response=False)
        self.assertEqual(messages(response), ["Access denied, sorry."])

    @override_settings(
        FEATURES={"yes": True, "no": False, "maybe": {"test@example.com"}}
    )
    def test_user_features(self):
        user = User(email="test@example.org")
        self.assertTrue(user.features["yes"])
        self.assertFalse(user.features["no"])
        self.assertFalse(user.features["maybe"])

        user = User(email="test@example.com")
        self.assertTrue(user.features["yes"])
        self.assertFalse(user.features["no"])
        self.assertTrue(user.features["maybe"])
