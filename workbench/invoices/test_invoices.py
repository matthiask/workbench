from datetime import date
from decimal import Decimal

from django.test import TestCase

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.tools.forms import WarningsForm
from workbench.tools.formats import local_date_format
from workbench.tools.testing import messages


def invoice_to_dict(invoice, **kwargs):
    return {
        "customer": invoice.customer_id or "",
        "contact": invoice.contact_id or "",
        "title": invoice.title,
        "description": invoice.description,
        "owned_by": invoice.owned_by_id,
        "subtotal": invoice.subtotal,
        "discount": invoice.discount,
        "third_party_costs": invoice.third_party_costs,
        "liable_to_vat": invoice.liable_to_vat,
        "postal_address": invoice.postal_address,
        "status": invoice.status,
        "type": invoice.type,
        "closed_on": invoice.closed_on and local_date_format(invoice.closed_on) or "",
        "invoiced_on": invoice.invoiced_on
        and local_date_format(invoice.invoiced_on)
        or "",
        "due_on": invoice.due_on and local_date_format(invoice.due_on) or "",
        **kwargs,
    }


class InvoicesTest(TestCase):
    def test_factories(self):
        invoice = factories.InvoiceFactory.create()

        self.client.force_login(invoice.owned_by)
        self.client.get(invoice.urls.url("detail"))

        response = self.client.post(invoice.urls.url("delete"))
        self.assertRedirects(
            response, invoice.urls.url("list"), fetch_redirect_response=False
        )

    def test_down_payment_invoice(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        url = project.urls["createinvoice"] + "?type=down-payment"
        response = self.client.get(url)
        self.assertContains(response, "Anzahlung")

        response = self.client.post(
            url,
            {
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "discount": 0,
                "liable_to_vat": 1,
                "postal_address": "Anything",
                "subtotal": 2500,
                "third_party_costs": 0,
            },
        )

        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertAlmostEqual(invoice.subtotal, Decimal("2500"))

    def create_service_invoice(self, params):
        service = factories.ServiceFactory.create(cost=100)
        url = service.project.urls.url("createinvoice") + params

        self.client.force_login(service.project.owned_by)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        return self.client.post(
            url,
            {
                "contact": service.project.contact_id,
                "title": service.project.title,
                "owned_by": service.project.owned_by_id,
                "discount": "0",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                "selected_services": [service.pk],
            },
        )

    def test_create_service_invoice_from_offer(self):
        response = self.create_service_invoice("?type=services&source=offer")
        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls.url("detail"))
        self.assertEqual(invoice.subtotal, 100)

        service = invoice.services.get()
        response = self.client.post(
            service.urls["update"],
            {
                "title": service.title,
                "description": service.description,
                "effort_type": service.effort_type,
                "effort_rate": service.effort_rate or "",
                "effort_hours": service.effort_hours or "",
                "cost": service.cost or "",
                "third_party_costs": service.third_party_costs or "",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.assertRedirects(
            self.client.post(invoice.urls["delete"]), invoice.urls["list"]
        )
        self.assertEqual(Invoice.objects.count(), 0)

    def test_create_service_invoice_from_logbook(self):
        response = self.create_service_invoice("?type=services&source=logbook")
        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls.url("detail"))
        self.assertEqual(invoice.subtotal, 0)

        self.assertRedirects(
            self.client.post(invoice.urls["delete"]), invoice.urls["list"]
        )
        self.assertEqual(Invoice.objects.count(), 0)

    def test_delete_service_invoice_with_logs(self):
        service = factories.ServiceFactory.create()
        cost = factories.LoggedCostFactory.create(
            cost=150, project=service.project, service=service, description="this"
        )

        url = (
            service.project.urls.url("createinvoice") + "?type=services&source=logbook"
        )
        self.client.force_login(service.project.owned_by)
        response = self.client.post(
            url,
            {
                "contact": service.project.contact_id,
                "title": service.project.title,
                "owned_by": service.project.owned_by_id,
                "discount": "0",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                "selected_services": [service.pk],
            },
        )

        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertAlmostEqual(invoice.subtotal, Decimal(150))

        cost.refresh_from_db()
        self.assertEqual(cost.invoice_service.invoice, invoice)
        self.assertEqual(cost.invoice_service.project_service, service)

        response = self.client.post(invoice.urls["delete"])
        self.assertContains(
            response, "Logbuch-Einträge sind mit dieser Rechnung verbunden."
        )
        self.assertEqual(Invoice.objects.count(), 1)
        cost.refresh_from_db()
        self.assertTrue(cost.invoice_service)

        response = self.client.post(
            invoice.urls["delete"], {WarningsForm.ignore_warnings_id: "on"}
        )
        self.assertRedirects(response, invoice.urls["list"])
        self.assertEqual(
            messages(response),
            ["Rechnung '{}' wurde erfolgreich gelöscht.".format(invoice)],
        )

        cost.refresh_from_db()
        self.assertEqual(cost.invoice_service, None)

        # Creating the invoice again succeeds.
        response = self.client.post(
            url,
            {
                "contact": service.project.contact_id,
                "title": service.project.title,
                "owned_by": service.project.owned_by_id,
                "discount": "0",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                "selected_services": [service.pk],
            },
        )
        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertAlmostEqual(invoice.subtotal, Decimal(150))

    def test_create_person_invoice(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)

        # pre_form does not have these fields
        response = self.client.get(Invoice().urls["create"])
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        url = Invoice().urls.url("create") + "?contact={}".format(person.pk)
        response = self.client.get(url)
        self.assertContains(response, 'method="POST"')
        self.assertContains(response, 'id="id_postal_address"')
        postal_address = factories.PostalAddressFactory.create(person=person)
        response = self.client.get(url)
        self.assertNotContains(response, 'id="id_postal_address"')

        response = self.client.post(
            url,
            {
                "customer": person.organization_id,
                "contact": person.id,
                "title": "Stuff",
                "owned_by": person.primary_contact_id,
                "subtotal": "110",
                "discount": "10",
                "liable_to_vat": "1",
                "pa": postal_address.id,
            },
        )
        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls.url("detail"))
        self.assertAlmostEqual(invoice.total_excl_tax, Decimal("100"))
        self.assertAlmostEqual(invoice.total, Decimal("107.7"))

        pdf = self.client.get(invoice.urls["pdf"])
        self.assertEqual(pdf.status_code, 200)  # No crash

    def test_update_invoice(self):
        invoice = factories.InvoiceFactory.create()
        self.client.force_login(invoice.owned_by)
        response = self.client.post(invoice.urls["update"], invoice_to_dict(invoice))
        self.assertContains(response, "Kein Kontakt ausgewählt.")

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, **{WarningsForm.ignore_warnings_id: "on"}),
        )
        self.assertRedirects(response, invoice.urls["detail"])

        response = self.client.post(
            invoice.urls["update"], invoice_to_dict(invoice, status=Invoice.SENT)
        )
        self.assertContains(
            response,
            "Rechnungs- und/oder Fälligkeitsdatum fehlen für den augewählten Status.",
        )

        person = factories.PersonFactory.create(organization=invoice.customer)
        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(
                invoice,
                contact=person.id,
                status=Invoice.SENT,
                invoiced_on=local_date_format(date.today()),
                due_on=local_date_format(date.today()),
            ),
        )
        self.assertRedirects(response, invoice.urls["detail"])

        invoice.refresh_from_db()
        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, postal_address=invoice.postal_address + " hello"),
        )
        self.assertContains(
            response,
            "Du hast &#39;Postadresse&#39; geändert. Ich versuche,"
            " unabsichtliche Änderungen an Feldern",
        )

        response = self.client.post(
            invoice.urls["update"], invoice_to_dict(invoice, status=Invoice.PAID)
        )
        self.assertRedirects(response, invoice.urls["detail"])

        invoice.refresh_from_db()
        self.assertEqual(invoice.closed_on, date.today())

        # print(response, response.content.decode("utf-8"))
