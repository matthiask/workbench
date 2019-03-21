from datetime import date
from itertools import islice

from django.test import TestCase

from workbench.invoices.utils import next_valid_day, recurring


class UtilsTest(TestCase):
    def test_next_valid_day(self):
        self.assertEqual(next_valid_day(2016, 2, 28), date(2016, 2, 28))
        self.assertEqual(next_valid_day(2016, 2, 29), date(2016, 2, 29))

        self.assertEqual(next_valid_day(2017, 2, 28), date(2017, 2, 28))
        self.assertEqual(next_valid_day(2017, 2, 29), date(2017, 3, 1))

        # Days>31 may not increment months by more than 1
        self.assertEqual(next_valid_day(2018, 1, 65), date(2018, 2, 1))

        # Months>12 may increment years by more than 1
        self.assertEqual(next_valid_day(2018, 27, 1), date(2020, 3, 1))

    def test_recurring(self):
        self.assertEqual(
            list(islice(recurring(date(2016, 2, 29), "yearly"), 5)),
            [
                date(2016, 2, 29),
                date(2017, 3, 1),
                date(2018, 3, 1),
                date(2019, 3, 1),
                date(2020, 2, 29),
            ],
        )

        self.assertEqual(
            list(islice(recurring(date(2016, 1, 31), "quarterly"), 5)),
            [
                date(2016, 1, 31),
                date(2016, 5, 1),
                date(2016, 7, 31),
                date(2016, 10, 31),
                date(2017, 1, 31),
            ],
        )

        self.assertEqual(
            list(islice(recurring(date(2016, 1, 31), "monthly"), 5)),
            [
                date(2016, 1, 31),
                date(2016, 3, 1),
                date(2016, 3, 31),
                date(2016, 5, 1),
                date(2016, 5, 31),
            ],
        )

        self.assertEqual(
            list(islice(recurring(date(2016, 1, 1), "weekly"), 5)),
            [
                date(2016, 1, 1),
                date(2016, 1, 8),
                date(2016, 1, 15),
                date(2016, 1, 22),
                date(2016, 1, 29),
            ],
        )

        with self.assertRaises(ValueError):
            list(islice(recurring(date(2016, 1, 1), "unknown"), 5))
