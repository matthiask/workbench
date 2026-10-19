import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice


def previous_month():
    return (dt.date.today().replace(day=1) - dt.timedelta(days=1)).replace(day=1)


def deal(value, **kwargs):
    deal = factories.DealFactory.create(**kwargs)
    deal.values.create(type=factories.ValueTypeFactory.create(), value=value)
    deal.save()
    return deal


class KeyDataAPITest(TestCase):
    def test_authentication(self):
        """The key data API requires the configured bearer token"""
        url = "/api/key-data/"

        with override_settings(KEY_DATA_API_TOKEN=""):
            self.assertEqual(self.client.get(url).status_code, 403)
            response = self.client.get(url, headers={"Authorization": "Bearer "})
            self.assertEqual(response.status_code, 403)

        with override_settings(KEY_DATA_API_TOKEN="secret"):
            self.assertEqual(self.client.get(url).status_code, 403)
            response = self.client.get(url, headers={"Authorization": "Bearer nope"})
            self.assertEqual(response.status_code, 403)
            response = self.client.post(url, headers={"Authorization": "Bearer secret"})
            self.assertEqual(response.status_code, 405)

    @override_settings(KEY_DATA_API_TOKEN="secret")
    def test_key_data(self):
        """The key data API returns last month's figures"""
        month = previous_month()

        invoice = factories.InvoiceFactory.create(
            invoiced_on=month,
            subtotal=1000,
            third_party_costs=200,
            status=Invoice.SENT,
        )
        deal(
            5000,
            status=Deal.ACCEPTED,
            closed_on=month + dt.timedelta(days=3),
            customer=invoice.customer,
        )
        deal(
            3000,
            probability=Deal.HIGH,
            decision_expected_on=dt.date.today() + dt.timedelta(days=50),
        )
        deal(2000, probability=Deal.NORMAL)
        deal(1, probability=Deal.LOW)

        response = self.client.get(
            "/api/key-data/", headers={"Authorization": "Bearer secret"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["month"], f"{month:%Y-%m}")
        self.assertEqual(data["gross_margin"], 800.0)
        self.assertEqual(data["open_invoices_total_excl_tax"], 1000.0)
        self.assertEqual(
            data["deals_funnel"],
            {
                "high_probability_next_4_weeks": 0.0,
                "high_probability_next_12_weeks": 3000.0,
                "high_probability_later": 0.0,
                "normal_probability": 2000.0,
            },
        )
        self.assertEqual(len(data["accepted_deals"]), 1)
        self.assertEqual(data["accepted_deals"][0]["value"], 5000.0)
        self.assertEqual(
            data["accepted_deals"][0]["closed_on"],
            (month + dt.timedelta(days=3)).isoformat(),
        )
        self.assertEqual(
            [row["month"] for row in data["previous_months"]],
            [
                f"{(month - dt.timedelta(days=1)):%Y-%m}",
                f"{(month - dt.timedelta(days=32)).replace(day=1):%Y-%m}",
                f"{(month - dt.timedelta(days=63)).replace(day=1):%Y-%m}",
            ],
        )
        self.assertEqual(data["canceled_invoices_total_excl_tax"], 0.0)
        for key in [
            "green_hours_percentage",
            "accruals",
            "full_time_equivalents",
            "squeeze_gross_margin",
        ]:
            self.assertIn(key, data)

    @override_settings(KEY_DATA_API_TOKEN="secret")
    def test_canceled_invoices(self):
        """Invoices canceled last month are reported separately"""
        month = previous_month()

        factories.InvoiceFactory.create(
            invoiced_on=month - dt.timedelta(days=40),
            closed_on=month + dt.timedelta(days=5),
            subtotal=300,
            status=Invoice.CANCELED,
            payment_notice="Wrong customer",
        )
        factories.InvoiceFactory.create(
            invoiced_on=month - dt.timedelta(days=40),
            closed_on=month - dt.timedelta(days=5),
            subtotal=700,
            status=Invoice.CANCELED,
            payment_notice="Canceled before last month",
        )

        response = self.client.get(
            "/api/key-data/", headers={"Authorization": "Bearer secret"}
        )
        data = response.json()
        self.assertEqual(data["canceled_invoices_total_excl_tax"], 300.0)
        self.assertEqual(
            [
                row["canceled_invoices_total_excl_tax"]
                for row in data["previous_months"]
            ],
            [700.0, 0.0, 0.0],
        )
