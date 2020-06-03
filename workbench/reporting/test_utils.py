from django.test import TestCase
from django.utils.translation import deactivate_all

from time_machine import travel

from workbench.reporting.utils import date_ranges


class UtilsTest(TestCase):
    @travel("2020-02-25 12:00")
    def test_date_ranges(self):
        """The date ranges utility returns expected values"""
        deactivate_all()
        self.assertEqual(
            date_ranges(),
            [
                ("2020-02-24", "2020-03-01", "this week"),
                ("2020-02-17", "2020-02-23", "last week"),
                ("2020-02-01", "2020-02-29", "this month"),
                ("2020-01-01", "2020-01-31", "last month"),
                ("2020-01-01", "2020-03-31", "this quarter"),
                ("2019-10-01", "2019-12-31", "last quarter"),
                ("2020-01-01", "2020-12-31", "this year"),
                ("2019-01-01", "2019-12-31", "last year"),
            ],
        )
