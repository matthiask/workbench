import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from workbench import factories
from workbench.accounts.features import UnknownFeature
from workbench.accounts.models import User
from workbench.projects.models import Project
from workbench.tools.testing import messages


class AccountsTest(TestCase):
    def test_user(self):
        """User's methods and atttributes work as expected"""
        with self.assertRaises(ValueError):
            User.objects.create_user("", "")

        user = User.objects.create_user("test@example.com", "")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.has_perm("stuff"))
        self.assertTrue(user.has_module_perms("stuff"))
        self.assertFalse(user.is_staff)

    def test_admin(self):
        """Admin user's methods and atttributes work as expected"""
        user = User.objects.create_superuser("test@example.com", "")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.has_perm("stuff"))
        self.assertTrue(user.has_module_perms("stuff"))
        self.assertTrue(user.is_staff)

    def test_choices(self):
        """User.objects.choices() does what it should"""
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
        """Ordering of users while falling back to different attributes"""
        self.assertTrue(User(_short_name="a") < User(_full_name="b"))

    @override_settings(FEATURES={"glassfrog": False})
    def test_feature_required(self):
        """The feature_required decorator redirects users and adds a message"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get(reverse("report_hours_by_circle"))
        self.assertRedirects(response, "/")
        self.assertEqual(messages(response), ["Feature not available"])

    @override_settings(
        FEATURES={"yes": True, "no": False, "maybe": {"test@example.com"}}
    )
    def test_user_features(self):
        """Features may either be enabled for all, for some or for no users"""
        user = User(email="test@example.org")
        self.assertTrue(user.features["yes"])
        self.assertFalse(user.features["no"])
        self.assertFalse(user.features["maybe"])
        with self.assertRaises(UnknownFeature):
            user.features["missing"]

        user = User(email="test@example.com")
        self.assertTrue(user.features["yes"])
        self.assertFalse(user.features["no"])
        self.assertTrue(user.features["maybe"])
        with self.assertRaises(UnknownFeature):
            user.features["missing"]

    def test_profile(self):
        """The profile view doesn't crash"""
        hours = factories.LoggedHoursFactory.create()
        hours = factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(
                project=factories.ProjectFactory.create(type=Project.INTERNAL)
            ),
            rendered_by=hours.rendered_by,
        )
        self.client.force_login(hours.rendered_by)

        response = self.client.get("/profile/")
        self.assertContains(response, "Hours per week")

    def test_work_anniversaries(self):
        """The work anniversaries report doesn't crash"""
        user = factories.UserFactory.create()
        user.employments.create(
            percentage=100, vacation_weeks=5, date_from=dt.date(2018, 1, 1)
        )

        self.client.force_login(user)
        response = self.client.get("/report/work-anniversaries/")
        self.assertContains(response, user.get_full_name())
