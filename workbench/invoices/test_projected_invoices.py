from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.invoices.tasks import send_unsent_projected_invoices_reminders
from workbench.reporting.key_data import projected_gross_margin


class ProjectedInvoicesTest(TestCase):
    def setUp(self):
        deactivate_all()

    @travel("2021-11-30")
    def test_projected_invoices(self):
        """Functionality around projected gross margin and reminder mails"""
        obj = factories.ProjectedInvoiceFactory.create(gross_margin=Decimal(1000))
        pgm = projected_gross_margin()

        self.assertEqual(pgm["monthly_overall"][(2021, 11)], Decimal(1000))
        self.assertEqual(
            pgm["projects"],
            [
                {
                    "delta": Decimal("1000.00"),
                    "gross_margin": Decimal("0.00"),
                    "monthly": {(2021, 11): Decimal("1000.00")},
                    "project": obj.project,
                    "projected": [obj],
                    "projected_total": Decimal("1000.00"),
                }
            ],
        )

        send_unsent_projected_invoices_reminders()
        self.assertEqual(len(mail.outbox), 0)

        with travel("2021-12-01"):
            send_unsent_projected_invoices_reminders()
        self.assertEqual(len(mail.outbox), 0)

        with travel("2021-11-28"):
            send_unsent_projected_invoices_reminders()
        self.assertEqual(len(mail.outbox), 1)

        # print(mail.outbox[0].__dict__)

    def test_logged_third_party_costs_reduce_invoiced_gross_margin(self):
        """Logged third party costs exceeding those on invoices are deducted"""
        service = factories.ServiceFactory.create()
        project = service.project
        factories.ProjectedInvoiceFactory.create(
            project=project, gross_margin=Decimal(1000)
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.FIXED,
            subtotal=1000,
            status=Invoice.SENT,
        )
        factories.LoggedCostFactory.create(
            service=service, cost=300, third_party_costs=300
        )

        [row] = projected_gross_margin()["projects"]
        self.assertEqual(row["gross_margin"], 700)
        self.assertEqual(row["delta"], 300)

    @travel("2021-11-28")
    def test_reminder_explains_delta(self):
        """The reminder mail explains how the delta comes about"""
        service = factories.ServiceFactory.create()
        project = service.project
        factories.ProjectedInvoiceFactory.create(
            project=project,
            gross_margin=Decimal(1000),
            invoiced_on="2021-11-15",
        )
        factories.ProjectedInvoiceFactory.create(
            project=project,
            gross_margin=Decimal(500),
            invoiced_on="2022-01-15",
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.FIXED,
            subtotal=1000,
            third_party_costs=100,
            status=Invoice.SENT,
        )
        factories.LoggedCostFactory.create(
            service=service, cost=300, third_party_costs=300
        )

        send_unsent_projected_invoices_reminders()
        [message] = mail.outbox
        self.assertIn(
            "Geplanter bereinigter Umsatz bis 30.11.2021: 1’000.00", message.body
        )
        self.assertIn("Verrechnet exkl. MwSt.: 1’000.00", message.body)
        self.assertIn(
            "Fremdkosten: 300.00 (auf Rechnungen: 100.00, erfasst: 300.00)",
            message.body,
        )
        self.assertIn("Verrechneter bereinigter Umsatz: 700.00", message.body)
        self.assertIn("Delta: 300.00", message.body)

    def test_projected_warning_third_party_costs(self):
        """Projected invoices are compared to the gross margin of services"""
        service = factories.ServiceFactory.create(
            cost=Decimal(10000), third_party_costs=Decimal(5000)
        )
        project = service.project
        pi = factories.ProjectedInvoiceFactory.create(
            project=project, gross_margin=Decimal(5000)
        )
        self.client.force_login(project.owned_by)

        def projected_warning():
            response = self.client.get(project.get_absolute_url())
            return response.context["projected_warning"]

        self.assertIsNone(projected_warning())

        pi.gross_margin = Decimal(2000)
        pi.save()
        self.assertEqual(projected_warning(), "incomplete")
        response = self.client.get(project.get_absolute_url())
        self.assertContains(response, "(10’000.00 &minus;")
        self.assertContains(response, "5’000.00 third party costs)")

        pi.gross_margin = Decimal(6000)
        pi.save()
        self.assertEqual(projected_warning(), "exceeds_service_cost")
