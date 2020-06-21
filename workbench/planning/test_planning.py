import datetime as dt

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories


class PlanningTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_no_monday(self):
        """Non-mondays are rejected from PlannedWork.weeks"""
        pw = factories.PlannedWorkFactory.create(weeks=[dt.date(2020, 6, 21)])

        msg = ["Only mondays allowed, but field contains 21.06.2020."]

        with self.assertRaises(ValidationError) as cm:
            pw.clean_fields(exclude=["weeks"])
        self.assertEqual(list(cm.exception), msg)
