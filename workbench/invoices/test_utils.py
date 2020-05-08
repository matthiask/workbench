import datetime as dt
from itertools import islice

from django.test import TestCase

from workbench.invoices.utils import next_valid_day, recurring


class UtilsTest(TestCase):
    def test_next_valid_day(self):
        """The next_valid_day returns valid days :-)"""
        self.assertEqual(next_valid_day(2016, 2, 28), dt.date(2016, 2, 28))
        self.assertEqual(next_valid_day(2016, 2, 29), dt.date(2016, 2, 29))

        self.assertEqual(next_valid_day(2017, 2, 28), dt.date(2017, 2, 28))
        self.assertEqual(next_valid_day(2017, 2, 29), dt.date(2017, 3, 1))

        # Days>31 may not increment months by more than 1
        self.assertEqual(next_valid_day(2018, 1, 65), dt.date(2018, 2, 1))

        # Months>12 may increment years by more than 1
        self.assertEqual(next_valid_day(2018, 27, 1), dt.date(2020, 3, 1))

    def test_recurring(self):
        """The recurring() utilty returns expected values"""
        self.assertEqual(
            list(islice(recurring(dt.date(2016, 2, 29), "yearly"), 5)),
            [
                dt.date(2016, 2, 29),
                dt.date(2017, 3, 1),
                dt.date(2018, 3, 1),
                dt.date(2019, 3, 1),
                dt.date(2020, 2, 29),
            ],
        )

        self.assertEqual(
            list(islice(recurring(dt.date(2016, 1, 31), "quarterly"), 5)),
            [
                dt.date(2016, 1, 31),
                dt.date(2016, 5, 1),
                dt.date(2016, 7, 31),
                dt.date(2016, 10, 31),
                dt.date(2017, 1, 31),
            ],
        )

        self.assertEqual(
            list(islice(recurring(dt.date(2016, 1, 31), "monthly"), 5)),
            [
                dt.date(2016, 1, 31),
                dt.date(2016, 3, 1),
                dt.date(2016, 3, 31),
                dt.date(2016, 5, 1),
                dt.date(2016, 5, 31),
            ],
        )

        self.assertEqual(
            list(islice(recurring(dt.date(2016, 1, 1), "weekly"), 5)),
            [
                dt.date(2016, 1, 1),
                dt.date(2016, 1, 8),
                dt.date(2016, 1, 15),
                dt.date(2016, 1, 22),
                dt.date(2016, 1, 29),
            ],
        )

        with self.assertRaises(ValueError):
            list(islice(recurring(dt.date(2016, 1, 1), "unknown"), 5))
