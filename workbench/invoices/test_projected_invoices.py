from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench import factories
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
                    "invoiced": [],
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

        pi.gross_margin = Decimal(6000)
        pi.save()
        self.assertEqual(projected_warning(), "exceeds_service_cost")
