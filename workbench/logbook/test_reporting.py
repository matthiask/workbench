import datetime as dt
from decimal import Decimal

from django.test import TestCase

from workbench import factories
from workbench.logbook.reporting import classify_logging_delay, logbook_stats
from workbench.tools.formats import Z1


class ReportingTest(TestCase):
    def test_report(self):
        """Smoke test the logging stats report"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        factories.LoggedHoursFactory.create()

        response = self.client.get("/report/logging/")
        self.assertContains(response, "Logging statistics")

    def test_stats(self):
        """_Very_ basic testing of logged hours statistics"""
        stats = logbook_stats([dt.date.today(), dt.date.today()])

        self.assertEqual(len(stats["users"]), 0)
        self.assertEqual(
            stats["logged_hours_stats"], {"count": 0, "sum": Z1, "avg": None}
        )

        factories.LoggedHoursFactory.create()
        factories.LoggedHoursFactory.create()

        stats = logbook_stats([dt.date.today(), dt.date.today()])

        self.assertEqual(len(stats["users"]), 2)
        self.assertEqual(
            stats["users"][0]["logged_hours_stats"],
            {"avg": Decimal("1"), "count": 1, "sum": Decimal("1.0")},
        )

    def test_classify_logging_delay(self):
        """Logging delay classification"""
        self.assertEqual(classify_logging_delay(Decimal(-1))[1], "success")
        self.assertEqual(classify_logging_delay(Decimal(4))[1], "light")
        self.assertEqual(classify_logging_delay(Decimal(10))[1], "caveat")
        self.assertEqual(classify_logging_delay(Decimal(40))[1], "danger")
