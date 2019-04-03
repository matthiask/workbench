import io
import os
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.test import TestCase

from workbench import factories
from workbench.credit_control.models import CreditEntry
from workbench.tools.formats import local_date_format
from workbench.tools.testing import messages


class CreditEntriesTest(TestCase):
    def test_assignment(self):
        for i in range(10):
            invoice = factories.InvoiceFactory.create(
                subtotal=10 + i, liable_to_vat=False
            )

        entry_0 = factories.CreditEntryFactory.create(total=12)
        entry_1 = factories.CreditEntryFactory.create(total=14)
        entry_2 = factories.CreditEntryFactory.create(total=19)

        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/credit-control/assign/")
        # print(response, response.content.decode("utf-8"))

        self.assertContains(response, "widget--radioselect", 3)
        response = self.client.post(
            "/credit-control/assign/",
            {
                "entry_{}_invoice".format(entry_2.pk): invoice.pk,
                "entry_{}_notes".format(entry_1.pk): "Stuff",
            },
        )
        self.assertRedirects(response, "/credit-control/assign/")

        response = self.client.get("/credit-control/assign/")
        self.assertContains(response, "widget--radioselect", 1)

        response = self.client.post(
            "/credit-control/assign/",
            {"entry_{}_notes".format(entry_0.pk): "Stuff"},
            follow=True,
        )
        self.assertRedirects(response, "/credit-control/")
        self.assertEqual(
            messages(response),
            [
                "Gutschriften wurden erfolgreich geändert.",
                "Alle Gutschriften wurden zugewiesen.",
            ],
        )

    def test_account_statement_upload(self):
        self.client.force_login(factories.UserFactory.create())
        ledger = factories.LedgerFactory.create()

        response = self.client.get("/credit-control/upload/")
        # Not required!
        self.assertContains(
            response,
            '<input type="text" name="statement_data" class="form-control" id="id_statement_data">',  # noqa
            html=True,
        )

        with io.open(
            os.path.join(
                settings.BASE_DIR, "workbench", "test", "account-statement.csv"
            )
        ) as f:
            response = self.client.post(
                "/credit-control/upload/", {"statement": f, "ledger": ledger.pk}
            )

        self.assertContains(response, "reference_number")
        statement_data = response.context_data["form"].data["statement_data"]

        response = self.client.post(
            "/credit-control/upload/",
            {"statement_data": statement_data, "ledger": ledger.pk},
        )

        self.assertRedirects(response, "/credit-control/")
        self.assertEqual(messages(response), ["2 Gutschriften erstellt."])

        response = self.client.post(
            "/credit-control/upload/",
            {"statement_data": statement_data, "ledger": ledger.pk},
        )
        self.assertRedirects(response, "/credit-control/")
        self.assertEqual(messages(response), ["0 Gutschriften erstellt."])

        invoice = factories.InvoiceFactory.create(
            subtotal=Decimal("4000"), _code="00001"
        )
        self.assertAlmostEqual(invoice.total, Decimal("4308.00"))
        response = self.client.get("/credit-control/assign/")
        self.assertContains(response, "<strong><small>00001</small>")

        entry = CreditEntry.objects.get(reference_number="xxxx03130CF54579")
        response = self.client.post(
            entry.urls["update"],
            {
                "ledger": entry.ledger_id,
                "reference_number": entry.reference_number,
                "value_date": entry.value_date,
                "total": entry.total,
                "payment_notice": entry.payment_notice,
                "invoice": invoice.id,
                "notes": "",
            },
        )
        self.assertRedirects(response, entry.urls["detail"])

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, invoice.PAID)
        self.assertEqual(invoice.closed_on, entry.value_date)

    def test_list(self):
        self.client.force_login(factories.UserFactory.create())

        def valid(p):
            self.assertEqual(self.client.get("/credit-control/?" + p).status_code, 200)

        valid("")
        valid("s=pending")
        valid("s=processed")
        valid("xlsx=1")

    def test_create_entry(self):
        self.client.force_login(factories.UserFactory.create())

        response = self.client.post(
            "/credit-control/create/",
            {
                "ledger": factories.LedgerFactory.create().pk,
                "reference_number": "unique",
                "value_date": local_date_format(date.today()),
                "total": "20.55",
                "payment_notice": "nothing",
                "notes": "bla",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry = CreditEntry.objects.get()
        self.assertRedirects(response, entry.urls["list"])
