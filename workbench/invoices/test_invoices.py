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

    def test_create_service_invoice_from_offer(self):
        service = factories.ServiceFactory.create(cost=100)
        url = service.project.urls["createinvoice"] + "?type=services&source=offer"
        self.client.force_login(service.project.owned_by)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

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
        project = factories.ProjectFactory.create()
        service1 = factories.ServiceFactory.create(
            project=project, title="cost-only", cost=100
        )
        service2 = factories.ServiceFactory.create(project=project, title="no-rate")
        service3 = factories.ServiceFactory.create(
            project=project,
            title="with-rate",
            effort_type="Consulting",
            effort_rate=200,
        )
        service4 = factories.ServiceFactory.create(project=project, title="nothing")

        cost = factories.LoggedCostFactory.create(
            project=project, cost=10, description="Test"
        )
        hours = factories.LoggedHoursFactory.create(
            service=service1, hours=1, description="Test"
        )
        factories.LoggedHoursFactory.create(service=service2, hours=2)
        factories.LoggedHoursFactory.create(service=service3, hours=3)

        url = project.urls["createinvoice"] + "?type=services&source=logbook"
        self.client.force_login(project.owned_by)
        response = self.client.get(url)
        # print(response, response.content.decode("utf-8"))

        self.assertContains(response, "<strong>cost-only</strong><br>100.00")
        self.assertContains(response, "1.0h erfasst aber kein Stundensatz definiert.")
        self.assertContains(response, "<strong>no-rate</strong><br>0.00")
        self.assertContains(response, "2.0h erfasst aber kein Stundensatz definiert.")
        self.assertContains(response, "<strong>with-rate</strong><br>600.00")
        self.assertContains(
            response,
            "<strong>Nicht mit einer bestimmten Leistung verbunden.</strong><br>0.00",
        )
        self.assertContains(
            response,
            "10.00 erfasst aber nicht mit einer bestimmten Leistung verbunden.",
        )

        cost.service = service1
        cost.save()

        response = self.client.post(
            url,
            {
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "discount": "0",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                "selected_services": [
                    service1.pk,
                    service2.pk,
                    service3.pk,
                    service4.pk,
                ],
            },
        )
        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertEqual(invoice.subtotal, 610)

        cost.refresh_from_db()
        self.assertEqual(cost.invoice_service.invoice, invoice)
        hours.refresh_from_db()
        self.assertEqual(hours.invoice_service.invoice, invoice)

        self.assertEqual(service1.invoice_services.get().invoice, invoice)
        self.assertEqual(service2.invoice_services.get().invoice, invoice)
        self.assertEqual(service3.invoice_services.get().invoice, invoice)
        self.assertEqual(service4.invoice_services.count(), 0)

        response = self.client.post(
            cost.urls["update"],
            {
                "service": cost.service_id,
                "rendered_on": local_date_format(cost.rendered_on),
                "third_party_costs": cost.third_party_costs or "",
                "cost": 2 * cost.cost,
                "description": cost.description,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dieser Eintrag ist schon Teil einer Rechnung.")

        response = self.client.post(
            hours.urls["update"],
            {
                "service": hours.service_id,
                "rendered_on": local_date_format(hours.rendered_on),
                "rendered_by": hours.rendered_by_id,
                "hours": hours.hours,
                "description": hours.description,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dieser Eintrag ist schon Teil einer Rechnung.")

        response = self.client.post(
            cost.urls["update"],
            {
                # "service": cost.service_id,
                "rendered_on": local_date_format(cost.rendered_on),
                "third_party_costs": cost.third_party_costs or "",
                "cost": 2 * cost.cost,
                "description": cost.description,
                WarningsForm.ignore_warnings_id: "on",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        self.assertContains(
            self.client.get("/"),
            "Erfasste Kosten &#39;Test&#39; wurde erfolgreich geändert.",
        )

        cost.refresh_from_db()
        self.assertAlmostEqual(cost.cost, Decimal("20"))
        invoice.refresh_from_db()
        self.assertAlmostEqual(invoice.subtotal, 610)  # unchanged

        response = self.client.post(
            invoice.urls["delete"], {WarningsForm.ignore_warnings_id: "on"}
        )
        self.assertRedirects(response, invoice.urls["list"])
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(
            messages(response),
            ["Rechnung '{}' wurde erfolgreich gelöscht.".format(invoice)],
        )

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

        response = self.client.get(invoice.urls["delete"])
        self.assertContains(response, WarningsForm.ignore_warnings_id)

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

    def test_pre_form(self):
        self.client.force_login(factories.UserFactory.create())

        # pre_form does not have these fields
        response = self.client.get(Invoice().urls["create"])
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        # Nonexistant entries
        response = self.client.get(Invoice().urls["create"] + "?contact=0")
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        response = self.client.get(Invoice().urls["create"] + "?customer=0")
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        response = self.client.get(Invoice().urls["create"] + "?copy_invoice=0")
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

    def test_create_update_person_invoice(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)

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

        response = self.client.get(invoice.urls["update"])
        self.assertContains(response, 'id="id_postal_address"')
        self.assertNotContains(response, 'id="id_pa_0"')

        invoice.postal_address = ""
        invoice.save()

        response = self.client.get(invoice.urls["update"])
        self.assertNotContains(response, 'id="id_postal_address"')
        self.assertContains(response, 'id="id_pa_0"')

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

        response = self.client.get(invoice.urls["delete"])
        self.assertEqual(response.status_code, 200)

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

        response = self.client.get(invoice.urls["delete"])
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertEqual(
            messages(response),
            ["Rechnungen in Vorbereitung können gelöscht werden, andere nicht."],
        )

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

        with self.assertRaises(ValidationError) as cm:
            Invoice(
                title="Test",
                customer=factories.OrganizationFactory.create(),
                owned_by=factories.UserFactory.create(),
                type=Invoice.FIXED,
                _code=0,
                status=Invoice.SENT,
                invoiced_on=date.today(),
                due_on=date.today() - timedelta(days=1),
            ).full_clean()
        self.assertEqual(
            list(cm.exception),
            [("due_on", ["Fälligkeitsdatum muss später als Rechnungsdatum sein."])],
        )

        with self.assertRaises(ValidationError) as cm:
            Invoice(
                title="Test",
                customer=factories.OrganizationFactory.create(),
                owned_by=factories.UserFactory.create(),
                type=Invoice.DOWN_PAYMENT,
                _code=0,
                status=Invoice.IN_PREPARATION,
            ).full_clean()
        self.assertEqual(
            list(cm.exception),
            [
                (
                    "__all__",
                    ["Rechnungen vom Typ Anzahlung benötigen zwingend ein Projekt."],
                )
            ],
        )

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

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(
                invoice,
                status=Invoice.IN_PREPARATION,
                **{WarningsForm.ignore_warnings_id: "on"}
            ),
        )
        self.assertRedirects(response, invoice.urls["detail"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.IN_PREPARATION)
        self.assertIsNone(invoice.closed_on)
        # print(response, response.content.decode("utf-8"))

    def test_down_payment(self):
        project = factories.ProjectFactory.create()
        down_payment = factories.InvoiceFactory.create(
            project=project, type=Invoice.DOWN_PAYMENT, subtotal=100
        )

        self.client.force_login(project.owned_by)
        url = project.urls["createinvoice"] + "?type=fixed"
        response = self.client.get(url)
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, down_payment.code)
        self.assertContains(response, down_payment.pretty_total_excl)
        self.assertContains(response, down_payment.pretty_status)

        response = self.client.get(url)
        self.assertContains(
            response, "Dieses Projekt hat schon eine Rechnung in Vorbereitung."
        )

        response = self.client.post(
            url,
            {
                "contact": project.contact_id,
                "title": project.title,
                "description": "bla",
                "owned_by": project.owned_by_id,
                "discount": 0,
                "liable_to_vat": 1,
                "postal_address": "Anything",
                "subtotal": 2500,
                "third_party_costs": 0,
                "apply_down_payment": [down_payment.pk],
                WarningsForm.ignore_warnings_id: "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        invoice = project.invoices.latest("pk")
        self.assertRedirects(response, invoice.urls["detail"])

        self.assertAlmostEqual(invoice.subtotal, 2500)
        self.assertAlmostEqual(invoice.total_excl_tax, 2400)
        self.assertEqual(self.client.get(invoice.urls["pdf"]).status_code, 200)

    def test_change_contact(self):
        invoice = factories.InvoiceFactory.create(title="Test", subtotal=20)
        self.client.force_login(invoice.owned_by)

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, contact=factories.PersonFactory.create().pk),
        )
        self.assertContains(
            response,
            "Der Kontakt Vorname Nachname gehört nicht zu The Organization Ltd.",
        )

    def test_status(self):
        today = date.today()
        yesterday = date.today() - timedelta(days=1)
        fmt = local_date_format(today)
        self.assertEqual(
            Invoice(status=Invoice.IN_PREPARATION).pretty_status,
            "In Vorbereitung seit {}".format(fmt),
        )
        self.assertEqual(
            Invoice(status=Invoice.SENT, invoiced_on=today).pretty_status,
            "Versendet am {}".format(fmt),
        )
        self.assertEqual(
            Invoice(
                status=Invoice.SENT,
                invoiced_on=yesterday,
                due_on=today - timedelta(days=5),
            ).pretty_status,
            "Versendet am {}, aber überfällig".format(local_date_format(yesterday)),
        )
        self.assertEqual(
            Invoice(
                status=Invoice.SENT,
                invoiced_on=yesterday,
                due_on=today - timedelta(days=5),
            ).status_css,
            "warning",
        )
        self.assertEqual(
            Invoice(
                status=Invoice.SENT, invoiced_on=yesterday, last_reminded_on=today
            ).pretty_status,
            "Versendet am {}, gemahnt am {}".format(local_date_format(yesterday), fmt),
        )
        self.assertEqual(
            Invoice(status=Invoice.PAID, closed_on=today).pretty_status,
            "Bezahlt am {}".format(fmt),
        )
        self.assertEqual(Invoice(status=Invoice.REPLACED).pretty_status, "Ersetzt")
