import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.test.utils import override_settings
from time_machine import travel

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import Project


AUTH = {"Authorization": "Bearer secret"}


def invoice(**kwargs):
    kwargs.setdefault("status", Invoice.SENT)
    if project := kwargs.get("project"):
        kwargs.setdefault("customer", project.customer)
        kwargs.setdefault("contact", project.contact)
    return factories.InvoiceFactory.create(**kwargs)


def offer(project, cost, status):
    offer = factories.OfferFactory.create(project=project, status=status)
    factories.ServiceFactory.create(project=project, offer=offer, cost=cost)
    offer.save()
    return offer


@override_settings(KEY_DATA_API_TOKEN="secret")
class CashDataAPITest(TestCase):
    def test_authentication(self):
        """The cash data API requires the key data API token"""
        url = "/api/cash-data/"
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.get(url, headers={"Authorization": "Bearer nope"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post(url, headers=AUTH).status_code, 405)
        response = self.client.get(url + "?date=2026-13-01", headers=AUTH)
        self.assertEqual(response.status_code, 400)

    @travel("2026-10-28 08:00")
    def test_open_invoices(self):
        """Open invoices are totalled and grouped by the ISO week they are due"""
        invoice(
            invoiced_on=dt.date(2026, 9, 1),
            due_on=dt.date(2026, 10, 7),
            subtotal=1000,
        )
        invoice(
            invoiced_on=dt.date(2026, 10, 1),
            due_on=dt.date(2026, 10, 31),
            subtotal=2000,
        )
        invoice(
            invoiced_on=dt.date(2026, 10, 1),
            due_on=dt.date(2026, 11, 1),
            subtotal=3000,
        )
        # Paid since monday: not open anymore at the time of the request
        invoice(
            invoiced_on=dt.date(2026, 10, 1),
            due_on=dt.date(2026, 10, 20),
            subtotal=500,
            status=Invoice.PAID,
            closed_on=dt.date(2026, 10, 27),
        )
        invoice(subtotal=700, status=Invoice.IN_PREPARATION)

        response = self.client.get("/api/cash-data/?date=2026-10-26", headers=AUTH)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["date"], "2026-10-26")
        self.assertEqual(data["currency"], "CHF")
        self.assertEqual(
            data["open_invoices"],
            {
                "total_excl_tax": 6000.0,
                "total_incl_tax": 6462.0,
                "overdue_incl_tax": 1077.0,
            },
        )
        self.assertEqual(
            data["receivables_by_due_week"],
            [
                {
                    "iso_year": 2026,
                    "iso_week": 41,
                    "amount_excl_tax": 1000.0,
                    "amount_incl_tax": 1077.0,
                },
                {
                    "iso_year": 2026,
                    "iso_week": 44,
                    "amount_excl_tax": 5000.0,
                    "amount_incl_tax": 5385.0,
                },
            ],
        )
        self.assertIn("accruals", data)

        # Earlier dates are reconstructed where possible
        data = self.client.get("/api/cash-data/?date=2026-10-19", headers=AUTH).json()
        self.assertEqual(data["open_invoices"]["total_excl_tax"], 6500.0)
        self.assertIsNone(data["planned_invoicing_by_month"])
        self.assertIsNone(data["planned_invoicing_overdue_excl_tax"])
        self.assertIsNone(data["accepted_offers_not_invoiced"])

    @travel("2026-10-28 08:00")
    def test_planned_invoicing_and_offers(self):
        """Planned invoicing per month and accepted offers not invoiced yet"""
        planned = factories.ProjectFactory.create()
        factories.ProjectedInvoiceFactory.create(
            project=planned,
            invoiced_on=dt.date(2026, 9, 15),
            gross_margin=Decimal(1000),
        )
        factories.ProjectedInvoiceFactory.create(
            project=planned,
            invoiced_on=dt.date(2026, 12, 15),
            gross_margin=Decimal(4000),
        )
        factories.ProjectedInvoiceFactory.create(
            project=planned,
            invoiced_on=dt.date(2027, 8, 15),
            gross_margin=Decimal(2000),
        )
        offer(planned, 10000, Offer.ACCEPTED)
        invoice(project=planned, subtotal=1500, due_on=dt.date(2026, 11, 1))

        unplanned = factories.ProjectFactory.create()
        offer(unplanned, 3000, Offer.ACCEPTED)
        offer(unplanned, 9000, Offer.OFFERED)

        data = self.client.get("/api/cash-data/", headers=AUTH).json()
        self.assertEqual(data["date"], "2026-10-28")
        self.assertEqual(
            data["planned_invoicing_by_month"],
            [
                {"month": "2026-10", "amount_excl_tax": 0.0},
                {"month": "2026-11", "amount_excl_tax": 0.0},
                {"month": "2026-12", "amount_excl_tax": 3500.0},
                {"month": "2027-01", "amount_excl_tax": 0.0},
                {"month": "2027-02", "amount_excl_tax": 0.0},
                {"month": "2027-03", "amount_excl_tax": 0.0},
                {"month": "2027-04", "amount_excl_tax": 0.0},
                {"month": "2027-05", "amount_excl_tax": 0.0},
                {"month": "2027-06", "amount_excl_tax": 0.0},
                {"month": "2027-07", "amount_excl_tax": 0.0},
                {"month": "2027-08", "amount_excl_tax": 2000.0},
            ],
        )
        self.assertEqual(
            data["accepted_offers_not_invoiced"],
            {
                "total_excl_tax": 11500.0,
                "not_in_planned_invoicing_excl_tax": 6000.0,
            },
        )

    @travel("2026-10-28 08:00")
    def test_internal_projects_are_ignored(self):
        """Internal projects don't count towards accruals"""
        internal = factories.ProjectFactory.create(type=Project.INTERNAL)
        invoice(project=internal, subtotal=1000, status=Invoice.PAID)

        data = self.client.get("/api/cash-data/", headers=AUTH).json()
        self.assertEqual(data["accruals"], 0.0)

    @travel("2026-10-28 08:00")
    def test_work_not_invoiced(self):
        """Work not invoiced yet, beyond the offers and covered by planned invoicing"""
        project = factories.ProjectFactory.create()
        accepted = factories.OfferFactory.create(project=project, status=Offer.ACCEPTED)
        service = factories.ServiceFactory.create(
            project=project,
            offer=accepted,
            effort_type="Any",
            effort_rate=100,
            effort_hours=10,
        )
        accepted.save()
        factories.LoggedHoursFactory.create(service=service, hours=15)
        factories.ProjectedInvoiceFactory.create(
            project=project,
            invoiced_on=dt.date(2026, 12, 15),
            gross_margin=Decimal(400),
        )
        # Internal projects are never invoiced
        factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(
                project=factories.ProjectFactory.create(type=Project.INTERNAL),
                effort_type="Any",
                effort_rate=100,
            ),
            hours=5,
        )

        data = self.client.get("/api/cash-data/", headers=AUTH).json()
        self.assertEqual(
            data["work_not_invoiced"],
            {
                "total_excl_tax": 1500.0,
                "beyond_offers_excl_tax": 500.0,
                "in_planned_invoicing_excl_tax": 400.0,
            },
        )

        data = self.client.get("/api/cash-data/?date=2026-10-19", headers=AUTH).json()
        self.assertIsNone(data["work_not_invoiced"])

    @travel("2026-10-28 08:00")
    def test_offers_not_in_planned_invoicing_are_gross_margin(self):
        """Third party costs in offers are not compared with planned gross margin"""
        project = factories.ProjectFactory.create()
        factories.ProjectedInvoiceFactory.create(
            project=project,
            invoiced_on=dt.date(2026, 12, 15),
            gross_margin=Decimal(6000),
        )
        accepted = factories.OfferFactory.create(project=project, status=Offer.ACCEPTED)
        factories.ServiceFactory.create(
            project=project, offer=accepted, cost=10000, third_party_costs=4000
        )
        accepted.save()

        data = self.client.get("/api/cash-data/", headers=AUTH).json()
        self.assertEqual(
            data["accepted_offers_not_invoiced"],
            {"total_excl_tax": 10000.0, "not_in_planned_invoicing_excl_tax": 0.0},
        )

    @travel("2026-10-28 08:00")
    def test_missed_planned_invoicing(self):
        """Planned invoicing from past months which hasn't happened is overdue"""
        project = factories.ProjectFactory.create()
        for invoiced_on, gross_margin in [
            (dt.date(2026, 6, 15), 1000),
            (dt.date(2026, 8, 15), 2000),
            (dt.date(2026, 11, 15), 4000),
        ]:
            factories.ProjectedInvoiceFactory.create(
                project=project,
                invoiced_on=invoiced_on,
                gross_margin=Decimal(gross_margin),
            )

        data = self.client.get("/api/cash-data/", headers=AUTH).json()
        self.assertEqual(
            data["planned_invoicing_by_month"][:2],
            [
                {"month": "2026-10", "amount_excl_tax": 0.0},
                {"month": "2026-11", "amount_excl_tax": 4000.0},
            ],
        )
        self.assertEqual(data["planned_invoicing_overdue_excl_tax"], 3000.0)

        # Invoicing 2500 consumes the oldest projections first
        invoice(project=project, subtotal=2500, due_on=dt.date(2026, 11, 1))
        data = self.client.get("/api/cash-data/", headers=AUTH).json()
        self.assertEqual(
            data["planned_invoicing_by_month"][:2],
            [
                {"month": "2026-10", "amount_excl_tax": 0.0},
                {"month": "2026-11", "amount_excl_tax": 4000.0},
            ],
        )
        self.assertEqual(data["planned_invoicing_overdue_excl_tax"], 500.0)
