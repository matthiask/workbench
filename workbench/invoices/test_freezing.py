import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.invoices.test_invoices import invoice_to_dict
from workbench.reporting.models import FreezeDate
from workbench.tools.validation import in_days


class FreezingTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_freezing(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        FreezeDate.objects.create(up_to=dt.date(2024, 12, 31))
        url = project.urls["createinvoice"] + "?type=fixed"

        # Directly creating the invoice fails.
        response = self.client.post(
            url,
            {
                "invoiced_on": "2024-12-31",
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "discount": 0,
                "liable_to_vat": "1",
                "tax_rate": "7.70",
                "postal_address": "Anything\nStreet\nCity",
                "subtotal": 2500,
                "third_party_costs": 0,
            },
        )
        self.assertContains(
            response,
            "Cannot create an invoice with a date of 31.12.2024 or earlier anymore.",
        )

        response = self.client.post(
            url,
            {
                "invoiced_on": "2025-01-01",
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "discount": 0,
                "liable_to_vat": "1",
                "tax_rate": "7.70",
                "postal_address": "Anything\nStreet\nCity",
                "subtotal": 2500,
                "third_party_costs": 0,
            },
        )

        invoice = Invoice.objects.get()

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice) | {"invoiced_on": "2024-12-31"},
        )
        self.assertContains(
            response,
            "Cannot create an invoice with a date of 31.12.2024 or earlier anymore.",
        )

        person = project.contact
        response = self.client.post(
            f"/recurring-invoices/create/?contact={person.pk}",
            {
                "customer": person.organization_id,
                "contact": person.id,
                "title": "recur",
                "owned_by": person.primary_contact_id,
                "starts_on": "2024-12-31",
                "periodicity": "yearly",
                "create_invoice_on_day": -20,
                "subtotal": 500,
                "discount": 0,
                "liable_to_vat": "1",
                "tax_rate": "7.70",
                "third_party_costs": 0,
                "postal_address": "Anything\nStreet\nCity",
            },
        )
        self.assertContains(
            response,
            "Cannot create a recurring invoice with a start date of 31.12.2024 or earlier anymore.",
        )

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                "closed_on": "2024-12-31",
            },
        )
        self.assertContains(
            response,
            "Cannot close a project with a date of 31.12.2024 or earlier anymore.",
        )
        # print(response, response.content.decode("utf-8"))

        project.closed_on = dt.date(2024, 12, 31)
        project.save()

        response = self.client.get(project.urls["update"])
        self.assertContains(
            response,
            "This project has been closed on or before 31.12.2024 and cannot be reopened anymore.",
        )

    def test_invoice_in_preparation_is_not_freezed(self):
        FreezeDate.objects.create(up_to=dt.date(2024, 12, 31))

        invoice = factories.InvoiceFactory.create(
            invoiced_on=dt.date(2024, 12, 15),
            postal_address="A\nB\nC",
        )

        self.client.force_login(invoice.owned_by)
        response = self.client.get(invoice.urls["update"])

        self.assertNotContains(
            response,
            "This invoice is freezed, only a small subset of fields are editable.",
        )

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice)
            | {
                "status": Invoice.SENT,
                "due_on": dt.date.today().isoformat(),
            },
        )
        self.assertContains(
            response,
            "Cannot create an invoice with a date of 31.12.2024 or earlier anymore.",
        )

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice)
            | {
                "status": Invoice.SENT,
                "invoiced_on": in_days(0).isoformat(),
                "due_on": in_days(15).isoformat(),
            },
        )
        self.assertRedirects(response, invoice.urls["detail"])

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.SENT)
        self.assertEqual(invoice.invoiced_on, in_days(0))

    def test_freezed_invoice_update(self):
        FreezeDate.objects.create(up_to=dt.date(2024, 12, 31))

        invoice = factories.InvoiceFactory.create(
            invoiced_on=dt.date(2024, 12, 15),
            due_on=dt.date(2025, 1, 1),
            status=Invoice.SENT,
            postal_address="A\nB\nC",
        )

        self.client.force_login(invoice.owned_by)
        response = self.client.get(invoice.urls["update"])

        self.assertContains(
            response,
            "This invoice is freezed, only a small subset of fields are editable.",
        )

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice)
            | {
                "status": Invoice.PAID,
                "closed_on": in_days(0).isoformat(),
                "payment_notice": "Whatevs",
            },
        )
        self.assertRedirects(response, invoice.urls["detail"])

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.PAID)
        self.assertEqual(invoice.closed_on, in_days(0))
        self.assertEqual(invoice.payment_notice, "Whatevs")
