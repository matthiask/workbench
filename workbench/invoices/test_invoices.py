from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.tools.formats import local_date_format
from workbench.tools.forms import WarningsForm
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
        self.client.get(invoice.urls["detail"])

        response = self.client.post(invoice.urls["delete"])
        self.assertRedirects(
            response, invoice.urls["list"], fetch_redirect_response=False
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
        url = service.project.urls["createinvoice"] + params

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
        self.assertRedirects(response, invoice.urls["detail"])
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
        self.assertRedirects(response, invoice.urls["detail"])
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

        url = service.project.urls["createinvoice"] + "?type=services&source=logbook"
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

        url = Invoice().urls["create"] + "?contact={}".format(person.pk)
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
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertAlmostEqual(invoice.total_excl_tax, Decimal("100"))
        self.assertAlmostEqual(invoice.total, Decimal("107.7"))

        pdf = self.client.get(invoice.urls["pdf"])
        self.assertEqual(pdf.status_code, 200)  # No crash

    def test_contact_check_with_project_invoice(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        url = project.urls["createinvoice"] + "?type=fixed"
        response = self.client.post(
            url,
            {
                "contact": factories.PersonFactory.create().pk,
                "title": "Stuff",
                "owned_by": project.owned_by_id,
                "subtotal": 100,
                "discount": 0,
                "liable_to_vat": 1,
                "postal_address": "Anything",
            },
        )
        self.assertContains(response, "gehört nicht zu")

    def test_update_invoice(self):
        invoice = factories.InvoiceFactory.create(contact=None)
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

    def test_list(self):
        factories.InvoiceFactory.create()
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def valid(p):
            self.assertEqual(self.client.get("/invoices/?" + p).status_code, 200)

        valid("")
        valid("s=all")
        valid("s=40")  # PAID
        valid("org={}".format(factories.OrganizationFactory.create().pk))
        valid("owned_by={}".format(user.id))
        valid("owned_by=0")  # only inactive
        valid("dunning=1")

    def test_model_validation(self):
        invoice = Invoice(
            title="Test",
            customer=factories.OrganizationFactory.create(),
            owned_by=factories.UserFactory.create(),
            type=Invoice.FIXED,
            _code=0,
            status=Invoice.SENT,
        )
        msg = [
            "Rechnungs- und/oder Fälligkeitsdatum fehlen für den augewählten Status."
        ]

        with self.assertRaises(ValidationError) as cm:
            invoice.clean_fields(exclude=["status"])
        self.assertEqual(list(cm.exception), msg)

        with self.assertRaises(ValidationError) as cm:
            invoice.clean_fields()
        self.assertEqual(list(cm.exception), [("status", msg)])

    def test_send_past_invoice(self):
        invoice = factories.InvoiceFactory.create(
            title="Test",
            subtotal=20,
            invoiced_on=date.today() - timedelta(days=1),
            due_on=date.today(),
        )
        self.client.force_login(invoice.owned_by)

        response = self.client.post(
            invoice.urls["update"], invoice_to_dict(invoice, status=Invoice.SENT)
        )
        self.assertContains(response, "Rechnungsdatum liegt in der Vergangenheit, aber")

    def test_unlock_sent_invoice(self):
        invoice = factories.InvoiceFactory.create(
            title="Test",
            subtotal=20,
            invoiced_on=date.today() - timedelta(days=1),
            due_on=date.today(),
            status=Invoice.SENT,
        )
        self.client.force_login(invoice.owned_by)

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, status=Invoice.IN_PREPARATION),
        )
        self.assertContains(
            response,
            "Status von &#39;Versendet&#39; zu &#39;In Vorbereitung&#39; ändern."
            " Bist Du sicher?",
        )

    def test_change_paid_invoice(self):
        invoice = factories.InvoiceFactory.create(
            title="Test",
            subtotal=20,
            invoiced_on=date.today() - timedelta(days=1),
            due_on=date.today(),
            closed_on=date.today(),
            status=Invoice.PAID,
        )
        self.client.force_login(invoice.owned_by)

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, status=Invoice.IN_PREPARATION),
        )
        self.assertContains(
            response,
            "Status von &#39;Bezahlt&#39; zu &#39;In Vorbereitung&#39; ändern."
            " Bist Du sicher?",
        )
        self.assertContains(
            response,
            "Du versuchst, den Status auf &#39;In Vorbereitung&#39; zu setzen,"
            " aber die Rechnung wurde schon am {} geschlossen."
            " Bist Du sicher?".format(local_date_format(date.today())),
        )

        # print(response, response.content.decode("utf-8"))
