import datetime as dt
import os
from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from workbench import factories
from workbench.credit_control.models import CreditEntry
from workbench.credit_control.parsers import (
    parse_postfinance_csv,
    postfinance_preprocess_notice,
    postfinance_reference_number,
)
from workbench.invoices.models import Invoice
from workbench.reporting.models import FreezeDate
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code, messages
from workbench.tools.validation import in_days


class CreditEntriesTest(TestCase):
    def test_assignment(self):
        """Batch assignment of credit entries to invoices"""
        for i in range(10):
            invoice = factories.InvoiceFactory.create(
                subtotal=10 + i,
                liable_to_vat=False,
                archived_at=timezone.now(),
                status=Invoice.SENT,
                due_on=in_days(30),
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
                f"entry_{entry_2.pk}_invoice": invoice.pk,
                f"entry_{entry_1.pk}_notes": "Stuff",
            },
        )
        self.assertRedirects(response, "/credit-control/assign/")

        response = self.client.get("/credit-control/assign/")
        self.assertContains(response, "widget--radioselect", 1)

        response = self.client.post(
            "/credit-control/assign/",
            {f"entry_{entry_0.pk}_notes": "Stuff"},
            follow=True,
        )
        self.assertRedirects(response, "/credit-control/")
        self.assertEqual(
            messages(response),
            [
                "credit entries have been updated successfully.",
                "All credit entries have already been assigned.",
            ],
        )

    def test_account_statement_upload(self):
        """Uploading account statements with and without duplicates"""
        self.client.force_login(factories.UserFactory.create())
        ledger = factories.LedgerFactory.create()

        def send(data=None):
            with open(
                os.path.join(
                    settings.BASE_DIR, "workbench", "test", "account-statement.csv"
                ),
                encoding="utf-8",
            ) as f:
                return self.client.post(
                    "/credit-control/upload/",
                    {"statement": f, "ledger": ledger.pk, **(data or {})},
                )

        response = send({"ledger": -1})
        self.assertContains(response, "Select a valid choice.")

        response = send()
        self.assertContains(response, "no-known-payments")

        response = send({WarningsForm.ignore_warnings_id: "no-known-payments"})

        # print(response, response.content.decode("utf-8"))
        self.assertRedirects(response, "/credit-control/")
        self.assertEqual(
            messages(response), ["Found 2 credit entries.", "Created 2 credit entries."]
        )

        response = send()

        self.assertRedirects(response, "/credit-control/")
        self.assertEqual(
            messages(response), ["Found 2 credit entries.", "Created 0 credit entries."]
        )

        invoice = factories.InvoiceFactory.create(
            subtotal=Decimal(4000),
            _code="00001",
            status=Invoice.SENT,
            due_on=in_days(30),
        )
        self.assertAlmostEqual(invoice.total, Decimal("4308.00"))
        response = self.client.get("/credit-control/assign/")
        self.assertContains(response, "<strong><small>00001</small>")

        entry = CreditEntry.objects.get(reference_number="BA22061438393")
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
        """Filter form validation"""
        self.client.force_login(factories.UserFactory.create())
        ledger = factories.LedgerFactory.create()

        code = check_code(self, "/credit-control/")
        code("")
        code("q=test")
        code("s=pending")
        code("s=processed")
        code(f"ledger={ledger.pk}")

    def test_create_entry(self):
        """Creating credit entries "by hand" works"""
        self.client.force_login(factories.UserFactory.create())

        response = self.client.post(
            "/credit-control/create/",
            {
                "ledger": factories.LedgerFactory.create().pk,
                "reference_number": "unique",
                "value_date": dt.date.today().isoformat(),
                "total": "20.55",
                "payment_notice": "nothing",
                "notes": "bla",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry = CreditEntry.objects.get()
        self.assertRedirects(response, entry.urls["list"])

    def test_assignment_of_invoice_with_credit_entry(self):
        """Invoices which have a credit entry already aren't offered again,
        e.g. after setting a paid invoice back to sent"""
        invoice = factories.InvoiceFactory.create(
            subtotal=10,
            liable_to_vat=False,
            status=Invoice.SENT,
            due_on=in_days(30),
        )
        factories.CreditEntryFactory.create(total=10, invoice=invoice)
        entry = factories.CreditEntryFactory.create(total=10)

        self.client.force_login(factories.UserFactory.create())
        response = self.client.post(
            "/credit-control/assign/", {f"entry_{entry.pk}_invoice": invoice.pk}
        )
        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertIsNone(entry.invoice)

    def test_payment_notice(self):
        """Assigning a credit entry adds its date, ledger, amount, payment
        notice and notes to the invoice's payment notice"""
        invoice = factories.InvoiceFactory.create(
            subtotal=10,
            liable_to_vat=False,
            status=Invoice.SENT,
            due_on=in_days(30),
            payment_notice="Paid in two parts",
        )
        entry = factories.CreditEntryFactory.create(
            total=10,
            value_date=dt.date(2026, 11, 3),
            payment_notice="ACME AG 2026-0001",
        )
        self.client.force_login(factories.UserFactory.create())
        response = self.client.post(
            "/credit-control/assign/",
            {
                f"entry_{entry.pk}_invoice": invoice.pk,
                f"entry_{entry.pk}_notes": "Second part",
            },
        )
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.PAID)
        self.assertEqual(
            invoice.payment_notice,
            "Paid in two parts\n\n"
            "03.11.2026, bank account, 10.00: ACME AG 2026-0001\nSecond part",
        )

    def test_payable_invoices(self):
        """Payments are only assigned to sent invoices, not to cancelled ones
        or to invoices in preparation (recurring invoices may create sent
        invoices directly)"""
        FreezeDate.objects.create(up_to=in_days(-30))
        canceled = factories.InvoiceFactory.create(
            subtotal=100, liable_to_vat=False, status=Invoice.CANCELED
        )
        without_date = factories.InvoiceFactory.create(
            subtotal=100, liable_to_vat=False, invoiced_on=None
        )
        frozen = factories.InvoiceFactory.create(
            subtotal=100, liable_to_vat=False, invoiced_on=in_days(-40)
        )
        in_preparation = factories.InvoiceFactory.create(
            subtotal=100, liable_to_vat=False
        )
        entry = factories.CreditEntryFactory.create(total=100)
        self.client.force_login(factories.UserFactory.create())

        for invoice in [canceled, without_date, frozen, in_preparation]:
            response = self.client.post(
                "/credit-control/assign/",
                {f"entry_{entry.pk}_invoice": invoice.pk},
            )
            self.assertContains(response, "Select a valid choice.")

            response = self.client.post(
                "/credit-control/create/",
                {
                    "ledger": entry.ledger_id,
                    "reference_number": f"unique-{invoice.pk}",
                    "value_date": dt.date.today().isoformat(),
                    "total": "100.00",
                    "payment_notice": "paid",
                    "invoice": invoice.pk,
                },
            )
            self.assertContains(
                response, "Payments can only be assigned to sent invoices"
            )
            status = invoice.status
            invoice.refresh_from_db()
            self.assertEqual(invoice.status, status)

    def test_unassign_warning(self):
        """Removing the invoice of a credit entry warns that the invoice stays
        paid"""
        invoice = factories.InvoiceFactory.create(
            subtotal=100,
            liable_to_vat=False,
            status=Invoice.PAID,
            due_on=in_days(30),
            closed_on=in_days(0),
        )
        entry = factories.CreditEntryFactory.create(total=100, invoice=invoice)
        self.client.force_login(factories.UserFactory.create())
        data = {
            "ledger": entry.ledger_id,
            "reference_number": entry.reference_number,
            "value_date": entry.value_date,
            "total": entry.total,
            "payment_notice": entry.payment_notice,
            "invoice": "",
            "notes": "",
        }
        response = self.client.post(entry.urls["update"], data)
        self.assertContains(response, "invoice-stays-paid")

        response = self.client.post(
            entry.urls["update"],
            data | {WarningsForm.ignore_warnings_id: "invoice-stays-paid"},
        )
        self.assertRedirects(response, entry.urls["detail"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.PAID)

    def test_postfinance_utilities(self):
        """Utilities for the PostFinance CSV export"""
        self.assertEqual(
            postfinance_preprocess_notice("bla 2019 -0001-0001 test"),
            "bla 2019-0001-0001 test",
        )
        self.assertEqual(
            postfinance_preprocess_notice("bla 2019-0001-0001 test"),
            "bla 2019-0001-0001 test",
        )
        self.assertEqual(
            postfinance_reference_number(
                "bla bla 190630CH12345678", dt.date(2019, 6, 30)
            ),
            "pf-190630CH12345678",
        )
        self.assertEqual(
            postfinance_reference_number(
                "bla 2019-0001-0001 test", dt.date(2019, 6, 30)
            ),
            "pf-ef8792bffe6303d32130377399828a3f",
        )

    def test_postfinance_parse_csv(self):
        """Generating PostFinance reference numbers when uploading acc. statements"""
        with open(
            os.path.join(
                settings.BASE_DIR, "workbench", "test", "postfinance-export.csv"
            ),
            "rb",
        ) as f:
            entries = parse_postfinance_csv(f.read())

        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["total"], Decimal("1193.30"))
        self.assertEqual(entries[0]["reference_number"], "pf-190618CH04D10XYZ")
        self.assertEqual(entries[0]["value_date"], dt.date(2019, 6, 18))

        self.assertEqual(
            entries[1]["reference_number"], "pf-bad7372a51d085b97f7b0e782841490b"
        )
        self.assertIn("2019-0015-0002", entries[1]["payment_notice"])

        self.assertEqual(
            entries[2]["reference_number"], "pf-d0436a6497bf533d2ae49809169f5481"
        )
        self.assertIn("2019-0214-0001", entries[2]["payment_notice"])

    def test_invalid_account_statement(self):
        """Completely invalid account statements do not crash the backend"""
        self.client.force_login(factories.UserFactory.create())
        ledger = factories.LedgerFactory.create()

        with open(
            os.path.join(settings.BASE_DIR, "workbench", "test", "stopwatch.png"), "rb"
        ) as f:
            response = self.client.post(
                "/credit-control/upload/", {"statement": f, "ledger": ledger.pk}
            )

        self.assertContains(response, "Error while parsing the statement.")

    def test_collision(self):
        """Selecting the same invoice in two credit entries doesn't crash"""

        invoice = factories.InvoiceFactory.create(
            subtotal=10,
            liable_to_vat=False,
            status=Invoice.SENT,
            due_on=in_days(30),
        )

        entry_0 = factories.CreditEntryFactory.create(total=10)
        entry_1 = factories.CreditEntryFactory.create(total=10)

        self.client.force_login(factories.UserFactory.create())
        response = self.client.post(
            "/credit-control/assign/",
            {
                f"entry_{entry_0.pk}_invoice": invoice.pk,
                f"entry_{entry_1.pk}_invoice": invoice.pk,
            },
        )
        # print(response, response.content.decode("utf-8"))
        self.assertContains(
            response,
            "This invoice has already been assigned to a previous credit entry in this form.",
        )
