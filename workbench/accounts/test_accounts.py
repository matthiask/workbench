from django.test import TestCase

from workbench import factories
from workbench.accounts.models import User


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
