import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench.invoices.models import Invoice


class PrettyLastRemindedOnTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        deactivate_all()

    def test_not_reminded_yet(self):
        invoice = Invoice(last_reminded_on=None)
        self.assertEqual(invoice.pretty_last_reminded_on, "Not reminded yet")

    def test_reminded_today(self):
        invoice = Invoice(last_reminded_on=dt.date.today())
        self.assertIn("today", invoice.pretty_last_reminded_on)

    def test_reminded_in_the_past(self):
        invoice = Invoice(last_reminded_on=dt.date.today() - dt.timedelta(days=3))
        result = invoice.pretty_last_reminded_on
        self.assertNotIn("today", result)
        self.assertIn("3", result)
