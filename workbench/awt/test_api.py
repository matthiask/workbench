import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories


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
            return [a["id"] for a in self.client.get(f"/api/absences/{query}").json()]

        self.assertEqual(ids(), [sick.pk, vacation.pk])
        self.assertEqual(ids("?since=2026-11-01"), [vacation.pk])
        self.assertEqual(ids("?until=2026-10-15"), [sick.pk])
        self.assertEqual(ids("?user=AB"), [vacation.pk])
        self.assertEqual(ids("?reason=sickness"), [sick.pk])

        data = self.client.get("/api/absences/?user=ab").json()[0]
        self.assertEqual(data["user"], "ab")
        self.assertEqual(data["days"], "10.00")
        self.assertEqual(data["description"], "Holidays")
