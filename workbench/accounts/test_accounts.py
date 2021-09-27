import datetime as dt

from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.forms import TeamForm, TeamSearchForm
from workbench.accounts.models import UnknownFeature, User
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

        self.client.force_login(user)

        # Contains the signed email value
        response = self.client.get(f"/admin/accounts/user/{user.pk}/change/")
        self.assertContains(response, f'<div class="readonly">{user.email}:')

        # Creating an user through the admin interface is possible
        wtm = factories.WorkingTimeModelFactory.create()
        data = {
            "email": "test@example.org",
            "language": "en",
            "working_time_model": wtm.id,
            "planning_hours_per_day": 6,
            "employments-TOTAL_FORMS": 0,
            "employments-INITIAL_FORMS": 0,
            "employments-MAX_NUM_FORMS": 1000,
            "vacation_days_overrides-TOTAL_FORMS": 0,
            "vacation_days_overrides-INITIAL_FORMS": 0,
            "vacation_days_overrides-MAX_NUM_FORMS": 1000,
            "_features": ["LATE_LOGGING"],
        }
        response = self.client.post("/admin/accounts/user/add/", data)
        self.assertEqual(response.status_code, 302)

        user = User.objects.latest("pk")
        self.assertEqual(user._features, ["LATE_LOGGING"])

    def test_choices(self):
        """User.objects.choices() does what it should"""
        u1 = factories.UserFactory.create(_full_name="M A", is_active=True)
        u2 = factories.UserFactory.create(_full_name="M I", is_active=False)

        self.assertEqual(
            list(User.objects.choices(collapse_inactive=False)),
            [
                ("", "Alle Nutzer*innen"),
                ("Aktiv", [(u1.pk, "M A")]),
                ("Inaktiv", [(u2.pk, "M I")]),
            ],
        )

        self.assertEqual(
            list(User.objects.choices(collapse_inactive=True)),
            [
                ("", "Alle Nutzer*innen"),
                (0, "Inaktive Nutzer*innen"),
                ("Aktiv", [(u1.pk, "M A")]),
            ],
        )

    def test_ordering(self):
        """Ordering of users while falling back to different attributes"""
        self.assertTrue(User(_short_name="a") < User(_full_name="b"))

    @override_settings(FEATURES={FEATURES.GLASSFROG: F.NEVER})
    def test_feature_required(self):
        """The feature_required decorator redirects users and adds a message"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get(reverse("report_hours_by_circle"))
        self.assertRedirects(response, "/")
        self.assertEqual(messages(response), ["Feature not available"])

    @override_settings(
        FEATURES={"yes": F.ALWAYS, "no": F.NEVER, "maybe": F.USER, "invalid": 42}
    )
    def test_user_features(self):
        """Features may either be enabled for all, for some or for no users"""
        user = User(email="test@example.org", _features=[])
        self.assertTrue(user.features["yes"])
        self.assertFalse(user.features["no"])
        self.assertFalse(user.features["maybe"])
        with self.assertRaises(UnknownFeature):
            user.features["missing"]

        user = User(email="test@example.com", _features=["maybe"])
        self.assertTrue(user.features["yes"])
        self.assertFalse(user.features["no"])
        self.assertTrue(user.features["maybe"])
        with self.assertRaises(UnknownFeature):
            user.features["missing"]

        with self.assertRaises(ValueError):
            user.features["invalid"]

    def test_user_views(self):
        """The user views do not crash"""
        hours = factories.LoggedHoursFactory.create()
        hours = factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(
                project=factories.ProjectFactory.create(type=Project.INTERNAL)
            ),
            rendered_by=hours.rendered_by,
        )
        self.client.force_login(hours.rendered_by)
        user = hours.rendered_by

        response = self.client.get("/users/")
        self.assertContains(response, user.get_full_name())

        response = self.client.get(f"/users/{user.id}/")
        self.assertContains(response, user.email)

        response = self.client.get(f"/users/{user.id}/statistics/")
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

    def test_team_crud(self):
        """CRUD of teams"""

        rf = RequestFactory()
        req = rf.get("/")

        form = TeamSearchForm(request=req)
        stuff = object()
        self.assertEqual(form.filter(stuff), stuff)

        user = factories.UserFactory.create()
        inactive = factories.UserFactory.create(is_active=False)

        form = TeamForm({"name": "A Team", "members": [user.id]}, request=req)
        self.assertEqual(set(form.fields["members"].queryset), {user})

        team = form.save()
        self.assertEqual(set(team.members.all()), {user})

        team.members.add(inactive)
        form = TeamForm(instance=team, request=req)
        self.assertEqual(set(form.fields["members"].queryset), {user, inactive})

    @override_settings(
        FEATURES={
            FEATURES.BOOKKEEPING: F.ALWAYS,
            FEATURES.BREAKS_NAG: F.NEVER,
            FEATURES.CAMPAIGNS: F.USER,
        }
    )
    def test_feature_admin(self):
        """Feature checkboxes in the user admin form are shown correctly"""
        user = factories.UserFactory.create(is_admin=True)
        self.client.force_login(user)

        response = self.client.get(f"/admin/accounts/user/{user.pk}/change/")
        self.assertContains(
            response,
            '<input type="checkbox" name="_features" value="BOOKKEEPING" checked disabled>',  # noqa
            html=True,
        )
        self.assertContains(
            response,
            '<input type="checkbox" name="_features" value="BREAKS_NAG" disabled>',  # noqa
            html=True,
        )
        self.assertContains(
            response,
            '<input type="checkbox" name="_features" value="CAMPAIGNS">',  # noqa
            html=True,
        )

        user._features.append(FEATURES.CAMPAIGNS)
        user.save()

        response = self.client.get(f"/admin/accounts/user/{user.pk}/change/")
        self.assertContains(
            response,
            '<input type="checkbox" name="_features" value="CAMPAIGNS" checked>',  # noqa
            html=True,
        )

    def test_coffee_feature(self):
        """Coffee feature activation and deactivation"""
        user = factories.UserFactory.create(_features=[FEATURES.BOOKKEEPING])
        self.client.force_login(user)
        self.assertEqual(user._features, [FEATURES.BOOKKEEPING])

        response = self.client.post(
            "/accounts/update/",
            {
                "_full_name": "Full Name",
                "_short_name": "FN",
                "language": "de",
                "planning_hours_per_day": 6,
                "feature_coffee": "on",
            },
        )
        self.assertRedirects(response, "/")

        user.refresh_from_db()
        self.assertEqual(user._features, [FEATURES.BOOKKEEPING, FEATURES.COFFEE])

        response = self.client.post(
            "/accounts/update/",
            {
                "_full_name": "Full Name",
                "_short_name": "FN",
                "language": "de",
                "planning_hours_per_day": 6,
                "feature_coffee": "",
            },
        )
        self.assertRedirects(response, "/")

        user.refresh_from_db()
        self.assertEqual(user._features, [FEATURES.BOOKKEEPING])
