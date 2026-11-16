from decimal import Decimal

from django.test import SimpleTestCase

from workbench.tools.formats import currency, currency_rounded, currency_thousands


class FormatsTest(SimpleTestCase):
    def test_currency(self):
        """Amounts have two decimals, reports may round to whole francs"""
        self.assertEqual(currency(Decimal("1234.5")), "1’234.50")
        self.assertEqual(currency_rounded(Decimal("1234.5")), "1’235")
        self.assertEqual(currency_rounded(Decimal("-0.4")), "0")
        self.assertEqual(currency_rounded(None), "0")
        self.assertEqual(currency_thousands(Decimal(113080)), "113.1")
        self.assertEqual(currency_thousands(Decimal(1234567)), "1’234.6")
        self.assertEqual(currency_thousands(None), "0.0")
