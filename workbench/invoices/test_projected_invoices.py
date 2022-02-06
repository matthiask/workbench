from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench import factories
from workbench.invoices.tasks import send_unsent_projected_invoices_reminders
from workbench.reporting.key_data import projected_invoices


class ProjectedInvoicesTest(TestCase):
    def setUp(self):
        deactivate_all()

    @travel("2021-11-30")
    def test_projected_invoices(self):
        """Functionality around projected invoices and reminder mails"""
        obj = factories.ProjectedInvoiceFactory.create(gross_margin=Decimal(1000))
        pi = projected_invoices()

        self.assertEqual(pi["monthly_overall"][(2021, 11)], Decimal(1000))
        self.assertEqual(
            pi["projects"],
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
