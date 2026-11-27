import datetime as dt

from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.middleware import set_user_name
from workbench.awt.changes import changes_by_others
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
        """Others' annual working time requires personnel administration
        like in the web interface"""
        user = factories.UserFactory.create(_short_name="ab")
        factories.UserFactory.create(_short_name="cd")
        self.client.force_login(user)

        response = self.client.get("/api/reports/working-time/", {"user": "AB"})
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/reports/working-time/", {"user": "CD"})
        self.assertEqual(response.status_code, 403)

    @override_settings(FEATURES={FEATURES.PERSONNEL_ADMINISTRATION: F.NEVER})
    def test_summary(self):
        """Everyone gets the summary of everyone, for planning"""
        user = factories.UserFactory.create(_short_name="ab")
        colleague = factories.UserFactory.create(_short_name="cd")
        for u in [user, colleague]:
            factories.YearFactory.create(
                year=2026, working_time_model=u.working_time_model
            )
            factories.EmploymentFactory.create(user=u, date_from=dt.date(2020, 1, 1))
        Absence.objects.create(
            user=colleague,
            starts_on=dt.date(2026, 11, 16),
            ends_on=dt.date(2026, 11, 20),
            days=5,
            reason=Absence.SICKNESS,
        )
        Absence.objects.create(
            user=colleague,
            starts_on=dt.date(2026, 10, 1),
            days=1,
            reason=Absence.SICKNESS,
        )
        self.client.force_login(user)

        with travel("2026-11-02 12:00"):
            response = self.client.get("/api/reports/working-time/", {"all": True})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["users"], [])
        summary = {row["user"]: row for row in data["summary"]}
        self.assertEqual(summary["cd"]["absences_planned"], "5.00")
        self.assertEqual(summary["cd"]["as_of"], "2026-10-31")
        self.assertNotIn("months", summary["cd"])

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

        # A blank short name identifies nobody, also not users without one
        factories.UserFactory.create(_short_name="")
        response = self.client.post(
            "/api/absences/",
            absence | {"user": ""},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)


@override_settings(FEATURES={FEATURES.PERSONNEL_ADMINISTRATION: F.USER})
class AbsenceChangeAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def patch(self, absence, data, query=""):
        return self.client.patch(
            f"/api/absences/{absence.pk}/{query}",
            data,
            content_type="application/json",
        )

    def test_update(self):
        """Absences are changed like in the web interface: by the person
        and by personnel administration, the person stays the same unless
        personnel administration changes it"""
        user = factories.UserFactory.create(_short_name="ab")
        absence = factories.AbsenceFactory.create(
            user=user, starts_on=dt.date.today(), days=1, reason=Absence.VACATION
        )
        self.client.force_login(user)

        response = self.patch(absence, {"days": "2"}, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["days"], "2.00")
        absence.refresh_from_db()
        self.assertEqual(absence.days, 1)

        response = self.patch(absence, {"days": "2", "description": "Beach"})
        self.assertEqual(response.status_code, 200, response.content)
        absence.refresh_from_db()
        self.assertEqual((absence.days, absence.description), (2, "Beach"))

        # The web interface doesn't hand absences over to others
        other = factories.UserFactory.create(_short_name="cd")
        response = self.patch(absence, {"user": "cd"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "data", "user"])
        self.assertIn("cannot be changed", response.content.decode())

        # Warnings are errors with a code
        far = (dt.date.today() + dt.timedelta(days=400)).isoformat()
        response = self.patch(absence, {"starts_on": far})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["code"], "impressive-planning-skills"
        )
        response = self.patch(
            absence,
            {"starts_on": far},
            "?ignore_warnings=impressive-planning-skills",
        )
        self.assertEqual(response.status_code, 200, response.content)

        # The absences of others are refused
        self.client.force_login(other)
        response = self.patch(absence, {"days": "1"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["path", "absence_id"])
        self.assertIn("absences of others", response.content.decode())

        # Personnel administration may, the change is reported to them
        hr = factories.UserFactory.create(_features=[FEATURES.PERSONNEL_ADMINISTRATION])
        self.client.force_login(hr)
        response = self.patch(
            absence, {"user": "cd", "starts_on": dt.date.today().isoformat()}
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["code"], "absence-of-others")
        response = self.patch(
            absence,
            {"user": "cd", "starts_on": dt.date.today().isoformat()},
            "?ignore_warnings=absence-of-others",
        )
        self.assertEqual(response.status_code, 200, response.content)
        absence.refresh_from_db()
        self.assertEqual(absence.user, other)

    def test_sickness(self):
        """Descriptions of sickness stay hidden from others, also when
        changing or deleting, and don't become visible by changing the
        reason"""
        user = factories.UserFactory.create(_short_name="ab")
        colleague = factories.UserFactory.create(_short_name="cd")
        set_user_name(user)
        sick = factories.AbsenceFactory.create(
            user=user,
            starts_on=dt.date.today(),
            reason=Absence.SICKNESS,
            description="Doctor's appointment",
        )
        self.client.force_login(user)

        response = self.patch(sick, {"reason": "paid"})
        self.assertEqual(response.status_code, 422)
        [error] = response.json()["detail"]
        self.assertEqual(error["loc"], ["body", "data", "reason"])
        self.assertIn("would become visible to everyone", error["msg"])
        self.assertNotIn("<a", error["msg"])
        response = self.patch(sick, {"reason": "paid", "description": None})
        self.assertEqual(response.status_code, 200, response.content)
        sick.refresh_from_db()
        self.assertEqual((sick.reason, sick.description), ("paid", ""))

        # Whoever entered someone's sickness may undo it on the same day,
        # without seeing the description in the response
        self.client.force_login(colleague)
        response = self.client.post(
            "/api/absences/",
            {
                "user": "ab",
                "starts_on": dt.date.today().isoformat(),
                "days": 1,
                "reason": "sickness",
                "description": "Flu",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        flu = Absence.objects.get(pk=response.json()["id"])
        response = self.patch(flu, {"days": "0.5"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["description"], "")
        response = self.client.delete(f"/api/absences/{flu.pk}/?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["description"], "")
        self.assertTrue(Absence.objects.filter(pk=flu.pk).exists())

        # The person sees it
        self.client.force_login(user)
        response = self.client.delete(f"/api/absences/{flu.pk}/?dry_run=true")
        self.assertEqual(response.json()["description"], "Flu")

    def test_delete(self):
        """Absences are deleted like in the web interface; deleting the
        absences of others is reported to personnel administration weekly
        (from the audit log), no mail is sent right away"""
        user = factories.UserFactory.create(_short_name="ab")
        colleague = factories.UserFactory.create(_short_name="cd")
        hr = factories.UserFactory.create(_features=[FEATURES.PERSONNEL_ADMINISTRATION])
        set_user_name(user)
        absence = factories.AbsenceFactory.create(
            user=user, starts_on=dt.date.today(), days=1, reason=Absence.VACATION
        )
        url = f"/api/absences/{absence.pk}/"

        self.client.force_login(colleague)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 422)
        self.assertIn("absences of others", response.content.decode())

        self.client.force_login(user)
        response = self.client.delete(url + "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], absence.pk)
        self.assertTrue(Absence.objects.filter(pk=absence.pk).exists())

        self.client.force_login(hr)
        start = timezone.now()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["user"], "ab")
        self.assertFalse(Absence.objects.filter(pk=absence.pk).exists())
        changes = changes_by_others(start, timezone.now() + dt.timedelta(seconds=1))
        self.assertEqual(
            [(row["kind"], row["owner"]) for row in changes["absences"]],
            [("D", user)],
        )
        self.assertEqual(len(mail.outbox), 0)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)
