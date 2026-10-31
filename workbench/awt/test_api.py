import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.awt.models import Absence, Holiday


class AbsencesAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_list(self):
        """Absences overlapping a period"""
        user = factories.UserFactory.create(_short_name="ab")
        vacation = factories.AbsenceFactory.create(
            user=user,
            starts_on=dt.date(2026, 10, 26),
            ends_on=dt.date(2026, 11, 6),
            days=10,
            description="Holidays",
        )
        sick = factories.AbsenceFactory.create(
            reason="sickness", starts_on=dt.date(2026, 10, 1), days=1
        )
        self.client.force_login(user)

        def ids(query=""):
            return [
                a["id"]
                for a in self.client.get(f"/api/absences/{query}").json()["items"]
            ]

        self.assertEqual(ids(), [sick.pk, vacation.pk])
        self.assertEqual(ids("?since=2026-11-01"), [vacation.pk])
        self.assertEqual(ids("?until=2026-10-15"), [sick.pk])
        self.assertEqual(ids("?user=AB"), [vacation.pk])
        self.assertEqual(ids("?reason=sickness"), [sick.pk])

        data = self.client.get("/api/absences/?user=ab").json()["items"][0]
        self.assertEqual(data["user"], "ab")
        self.assertEqual(data["days"], "10.00")
        self.assertEqual(data["description"], "Holidays")


class WorkingTimeAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    @travel("2026-03-04 12:00")
    def test_working_time(self):
        """Annual working time per month and week"""
        user = factories.UserFactory.create(_short_name="ab")
        factories.YearFactory.create(
            year=2026, working_time_model=user.working_time_model
        )
        factories.EmploymentFactory.create(
            user=user, date_from=dt.date(2026, 1, 1), percentage=50
        )
        Holiday.objects.create(
            working_time_model=user.working_time_model, date=dt.date(2026, 3, 2)
        )
        factories.LoggedHoursFactory.create(
            rendered_by=user, rendered_on=dt.date(2026, 3, 3), hours=6
        )
        factories.AbsenceFactory.create(
            user=user,
            starts_on=dt.date(2026, 3, 4),
            ends_on=dt.date(2026, 3, 5),
            days=2,
        )
        self.client.force_login(user)

        data = self.client.get("/api/reports/working-time/").json()
        self.assertEqual(data["year"], 2026)
        [row] = data["users"]
        self.assertEqual(row["user"], "ab")
        self.assertIsNone(row["weeks"])
        march = row["months"][2]
        self.assertEqual(march["month"], "2026-03")
        self.assertEqual(march["hours"], "6.0")
        self.assertEqual(march["vacation_days"], "2.00")
        self.assertEqual(march["absences_time"], "16.0")
        self.assertEqual(march["public_holiday_days"], "1.00")
        self.assertEqual(row["as_of"], "2026-02-28")
        self.assertEqual(
            row["totals"]["balance_as_of"], row["months"][1]["running_balance"]
        )
        self.assertEqual(row["totals"]["vacation_days_planned"], "1.00")

        data = self.client.get("/api/reports/working-time/", {"weekly": True}).json()
        week = data["users"][0]["weeks"][-1]
        # Monday is a holiday, Thursday is still in the future
        self.assertEqual(
            week,
            {
                "week": "2026-03-02",
                "target": "8.0",
                "hours": "6.0",
                "absences": "8.0",
                "delta": "6.0",
                "running_delta": week["running_delta"],
            },
        )
        self.assertEqual(data["users"][0]["weeks"][0]["week"], "2025-12-29")

    @override_settings(FEATURES={FEATURES.PERSONNEL_ADMINISTRATION: F.NEVER})
    def test_permissions(self):
        """The annual working time contains sickness absences, which are
        health data: Others' and everyone's require the personnel
        administration feature like in the web interface"""
        user = factories.UserFactory.create(_short_name="ab")
        factories.UserFactory.create(_short_name="cd")
        self.client.force_login(user)

        response = self.client.get("/api/reports/working-time/", {"user": "AB"})
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/reports/working-time/", {"user": "CD"})
        self.assertEqual(response.status_code, 403)
        response = self.client.get("/api/reports/working-time/", {"all": True})
        self.assertEqual(response.status_code, 403)

    @override_settings(FEATURES={FEATURES.PERSONNEL_ADMINISTRATION: F.ALWAYS})
    def test_permissions_personnel_administration(self):
        """Personnel administration sees everyone's annual working time"""
        user = factories.UserFactory.create()
        factories.UserFactory.create(_short_name="cd")
        self.client.force_login(user)

        response = self.client.get("/api/reports/working-time/", {"user": "CD"})
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/reports/working-time/", {"user": "xy"})
        self.assertEqual(response.status_code, 422)
        response = self.client.get("/api/reports/working-time/", {"all": True})
        self.assertEqual(response.status_code, 200)


class AbsenceCreateAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_create(self):
        """Absences are created like in the web interface"""
        user = factories.UserFactory.create(_short_name="ab")
        self.client.force_login(user)
        absence = {
            "starts_on": dt.date.today().isoformat(),
            "days": 1,
            "reason": "vacation",
            "description": "Holidays",
        }

        response = self.client.post(
            "/api/absences/?dry_run=true", absence, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["id"])
        self.assertFalse(Absence.objects.exists())

        response = self.client.post(
            "/api/absences/", absence, content_type="application/json"
        )
        self.assertEqual(response.json()["user"], "ab")
        self.assertEqual(Absence.objects.get().user, user)

        # Warnings of the web interface are errors
        far = dt.date.today() + dt.timedelta(days=400)
        response = self.client.post(
            "/api/absences/",
            absence | {"starts_on": far.isoformat()},
            content_type="application/json",
        )
        self.assertIn("Impressive planning skills", response.content.decode())
        self.assertEqual(response.status_code, 422)

        response = self.client.post(
            "/api/absences/",
            absence | {"ends_on": "2000-01-01"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        response = self.client.post(
            "/api/absences/",
            absence | {"user": "nobody"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
