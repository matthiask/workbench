import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.translation import deactivate_all

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
        "closed_on": invoice.closed_on and invoice.closed_on.isoformat() or "",
        "invoiced_on": invoice.invoiced_on and invoice.invoiced_on.isoformat() or "",
        "due_on": invoice.due_on and invoice.due_on.isoformat() or "",
        "show_service_details": invoice.show_service_details,
        **kwargs,
    }


class InvoicesTest(TestCase):
    fixtures = ["exchangerates.json"]

    def setUp(self):
        deactivate_all()

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
        self.assertContains(response, "Down payment")
        self.assertNotContains(response, "id_show_service_details")

        response = self.client.post(
            url,
            {
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "discount": 0,
                "liable_to_vat": 1,
                "postal_address": "Street\nCity",
                "subtotal": 2500,
                "third_party_costs": 0,
            },
        )
        self.assertContains(response, 'value="short-postal-address"')

        response = self.client.post(
            url,
            {
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "discount": 0,
                "liable_to_vat": 1,
                "postal_address": "Anything\nStreet\nCity",
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
        self.assertContains(response, "id_show_service_details")

        response = self.client.post(
            url,
            {
                "contact": service.project.contact_id,
                "title": service.project.title,
                "owned_by": service.project.owned_by_id,
                "discount": "0",
                "liable_to_vat": "1",
                "postal_address": "Anything\nStreet\nCity",
                "selected_services": [service.pk],
            },
        )
        # print(response, response.content.decode("utf-8"))

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
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

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
            service=service1, cost=10, description="Test"
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

        self.assertContains(response, "<strong>cost-only</strong><br>10.00")
        self.assertContains(response, "1.0h logged but no hourly rate defined.")
        self.assertContains(response, "<strong>no-rate</strong><br>0.00")
        self.assertContains(response, "2.0h logged but no hourly rate defined.")
        self.assertContains(response, "<strong>with-rate</strong><br>600.00")
        self.assertContains(response, "id_show_service_details")

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
                "postal_address": "Anything\nStreet\nCity",
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
                "rendered_on": cost.rendered_on.isoformat(),
                "third_party_costs": cost.third_party_costs or "",
                "cost": 2 * cost.cost,
                "description": cost.description,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This entry is already part of an invoice.")

        response = self.client.post(
            hours.urls["update"],
            {
                "service": hours.service_id,
                "rendered_on": hours.rendered_on.isoformat(),
                "rendered_by": hours.rendered_by_id,
                "hours": hours.hours,
                "description": hours.description,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This entry is already part of an invoice.")

        response = self.client.post(
            cost.urls["update"],
            {
                "modal-service": cost.service_id,
                "modal-rendered_by": cost.rendered_by_id,
                "modal-rendered_on": cost.rendered_on.isoformat(),
                "modal-third_party_costs": cost.third_party_costs or "",
                "modal-cost": 2 * cost.cost,
                "modal-description": cost.description,
                WarningsForm.ignore_warnings_id: "part-of-invoice",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        self.assertContains(
            self.client.get("/"),
            "logged cost &#x27;Test&#x27; has been updated successfully.",
        )

        cost.refresh_from_db()
        self.assertAlmostEqual(cost.cost, Decimal("20"))
        invoice.refresh_from_db()
        self.assertAlmostEqual(invoice.subtotal, 610)  # unchanged

        response = self.client.get(invoice.urls["pdf"])
        self.assertEqual(response.status_code, 200)  # No crash

        response = self.client.get(invoice.urls["xlsx"])
        self.assertEqual(response.status_code, 200)  # No crash

        response = self.client.post(
            invoice.urls["delete"],
            {WarningsForm.ignore_warnings_id: "release-logged-services"},
        )
        self.assertRedirects(response, invoice.urls["list"])
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(
            messages(response),
            ["invoice '{}' has been deleted successfully.".format(invoice)],
        )

    def test_delete_service_invoice_with_logs(self):
        service = factories.ServiceFactory.create()
        cost = factories.LoggedCostFactory.create(
            cost=150, service=service, description="this"
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
                "postal_address": "Anything\nStreet\nCity",
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
        self.assertContains(response, "Logged services are linked with this invoice.")
        self.assertEqual(Invoice.objects.count(), 1)
        cost.refresh_from_db()
        self.assertTrue(cost.invoice_service)

        response = self.client.post(
            invoice.urls["delete"],
            {WarningsForm.ignore_warnings_id: "release-logged-services"},
        )
        self.assertRedirects(response, invoice.urls["list"])
        self.assertEqual(
            messages(response),
            ["invoice '{}' has been deleted successfully.".format(invoice)],
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
                "postal_address": "Anything\nStreet\nCity",
                "selected_services": [service.pk],
            },
        )
        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertAlmostEqual(invoice.subtotal, Decimal(150))

    def test_pre_form(self):
        self.client.force_login(factories.UserFactory.create())

        # pre_form does not have these fields
        response = self.client.get(Invoice.urls["create"])
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        # Nonexistant entries
        response = self.client.get(Invoice.urls["create"] + "?contact=0")
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        response = self.client.get(Invoice.urls["create"] + "?customer=0")
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

    def test_create_update_person_invoice(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)

        url = Invoice.urls["create"] + "?contact={}".format(person.pk)
        response = self.client.get(url)
        self.assertContains(response, 'method="POST"')
        self.assertNotContains(response, 'data-field-value="')
        postal_address = factories.PostalAddressFactory.create(person=person)
        response = self.client.get(url)
        self.assertContains(response, 'data-field-value="', 1)

        person.organization.default_billing_address = "Default"
        person.organization.save()
        response = self.client.get(url)
        self.assertContains(response, 'data-field-value="', 2)

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
                "postal_address": postal_address.postal_address,
                "third_party_costs": 0,
            },
        )
        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertAlmostEqual(invoice.total_excl_tax, Decimal("100"))
        self.assertAlmostEqual(invoice.total, Decimal("107.7"))

    def test_customer_create_invoice(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)
        response = self.client.get(
            "/invoices/create/?customer={}".format(person.organization.id)
        )
        self.assertContains(
            response, 'value="The Organization Ltd" placeholder="organization"'
        )
        self.assertContains(response, 'id="id_postal_address"')
        self.assertNotContains(response, 'data-field-value="')
        self.assertNotContains(response, "id_show_service_details")

        person.organization.default_billing_address = "Default"
        person.organization.save()

        response = self.client.get(
            "/invoices/create/?customer={}".format(person.organization.id)
        )
        self.assertContains(response, 'id="id_postal_address"')
        self.assertContains(response, 'data-field-value="')

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
                "postal_address": "Anything\nStreet\nCity",
                "third_party_costs": 0,
            },
        )
        self.assertContains(response, "does not belong to")

    def test_update_invoice(self):
        invoice = factories.InvoiceFactory.create(
            contact=None, postal_address="Test\nStreet\nCity"
        )
        self.client.force_login(invoice.owned_by)
        response = self.client.post(invoice.urls["update"], invoice_to_dict(invoice))
        self.assertContains(response, "No contact selected.")

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, **{WarningsForm.ignore_warnings_id: "no-contact"}),
        )
        self.assertRedirects(response, invoice.urls["detail"])

        response = self.client.get(invoice.urls["delete"])
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            invoice.urls["update"], invoice_to_dict(invoice, status=Invoice.SENT)
        )
        self.assertContains(
            response, "Invoice and/or due date missing for selected state."
        )

        person = factories.PersonFactory.create(organization=invoice.customer)
        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(
                invoice,
                contact=person.id,
                status=Invoice.SENT,
                invoiced_on=dt.date.today().isoformat(),
                due_on=dt.date.today().isoformat(),
            ),
        )
        self.assertRedirects(response, invoice.urls["detail"])

        invoice.refresh_from_db()
        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, closed_on=dt.date.today().isoformat()),
        )
        self.assertContains(response, "Invalid status when closed on is already set.")

        response = self.client.get(invoice.urls["delete"])
        self.assertRedirects(response, invoice.urls["detail"])
        self.assertEqual(
            messages(response), ["Invoices in preparation may be deleted, others not."]
        )

        invoice.refresh_from_db()
        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, postal_address=invoice.postal_address + " hello"),
        )
        # print(response, response.content.decode("utf-8"))
        self.assertContains(
            response,
            "You are attempting to change &#x27;Postal address&#x27;."
            " I am trying to prevent unintentional changes. Are you sure?",
        )

        response = self.client.post(
            invoice.urls["update"], invoice_to_dict(invoice, status=Invoice.PAID)
        )
        self.assertRedirects(response, invoice.urls["detail"])

        invoice.refresh_from_db()
        self.assertEqual(invoice.closed_on, dt.date.today())

    def test_list(self):
        factories.InvoiceFactory.create()
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def valid(p):
            self.assertEqual(self.client.get("/invoices/?" + p).status_code, 200)

        valid("")
        valid("q=test")
        valid("s=open")
        valid("s=overdue")
        valid("s=40")  # PAID
        valid("org={}".format(factories.OrganizationFactory.create().pk))
        valid("owned_by={}".format(user.id))
        valid("owned_by=-1")  # mine
        valid("owned_by=0")  # only inactive

    def test_list_pdfs(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get("/invoices/?pdf=1")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(messages(response), ["No invoices found."])

        factories.InvoiceFactory.create(
            invoiced_on=dt.date.today() - dt.timedelta(days=60),
            due_on=dt.date.today() - dt.timedelta(days=45),
            status=Invoice.SENT,
        )
        response = self.client.get("/invoices/?pdf=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

        response = self.client.get("/invoices/?pdf=1&s=overdue")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

    def test_model_validation(self):
        invoice = Invoice(
            title="Test",
            customer=factories.OrganizationFactory.create(),
            owned_by=factories.UserFactory.create(),
            type=Invoice.FIXED,
            _code=0,
            status=Invoice.SENT,
            postal_address="Test\nStreet\nCity",
        )
        msg = ["Invoice and/or due date missing for selected state."]

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
                postal_address="Test\nStreet\nCity",
                invoiced_on=dt.date.today(),
                due_on=dt.date.today() - dt.timedelta(days=1),
            ).full_clean()
        self.assertEqual(
            list(cm.exception), [("due_on", ["Due date has to be after invoice date."])]
        )

        with self.assertRaises(ValidationError) as cm:
            Invoice(
                title="Test",
                customer=factories.OrganizationFactory.create(),
                owned_by=factories.UserFactory.create(),
                type=Invoice.DOWN_PAYMENT,
                _code=0,
                status=Invoice.IN_PREPARATION,
                postal_address="Test\nStreet\nCity",
            ).full_clean()
        self.assertEqual(
            list(cm.exception),
            [("__all__", ["Invoices of type Down payment require a project."])],
        )

    def test_unlock_sent_invoice(self):
        invoice = factories.InvoiceFactory.create(
            title="Test",
            subtotal=20,
            invoiced_on=dt.date.today() - dt.timedelta(days=1),
            due_on=dt.date.today(),
            status=Invoice.SENT,
        )
        self.client.force_login(invoice.owned_by)

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, status=Invoice.IN_PREPARATION),
        )
        self.assertContains(
            response,
            "Moving status from &#x27;Sent&#x27; to &#x27;In preparation&#x27;."
            " Are you sure?",
        )

    def test_change_paid_invoice(self):
        invoice = factories.InvoiceFactory.create(
            title="Test",
            subtotal=20,
            invoiced_on=dt.date.today() - dt.timedelta(days=1),
            due_on=dt.date.today(),
            closed_on=dt.date.today(),
            status=Invoice.PAID,
            postal_address="Test\nStreet\nCity",
        )
        self.client.force_login(invoice.owned_by)

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, status=Invoice.IN_PREPARATION),
        )
        self.assertContains(
            response,
            "Moving status from &#x27;Paid&#x27; to &#x27;In preparation&#x27;."
            " Are you sure?",
        )
        self.assertContains(
            response,
            "You are attempting to set status to &#x27;In preparation&#x27;,"
            " but the invoice has already been closed on {}."
            " Are you sure?".format(local_date_format(dt.date.today())),
        )

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(
                invoice,
                status=Invoice.IN_PREPARATION,
                **{
                    WarningsForm.ignore_warnings_id: (
                        "status-unexpected status-change-but-already-closed"
                    )
                }
            ),
        )
        # print(response, response.content.decode("utf-8"))
        self.assertRedirects(response, invoice.urls["detail"])
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.IN_PREPARATION)
        self.assertIsNone(invoice.closed_on)

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
            response, "This project already has an invoice in preparation."
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
                "postal_address": "Anything\nStreet\nCity",
                "subtotal": 2500,
                "third_party_costs": 0,
                "apply_down_payment": [down_payment.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        invoice = project.invoices.latest("pk")
        self.assertRedirects(response, invoice.urls["detail"])

        self.assertAlmostEqual(invoice.subtotal, 2500)
        self.assertAlmostEqual(invoice.total_excl_tax, 2400)
        self.assertEqual(self.client.get(invoice.urls["pdf"]).status_code, 200)

        response = self.client.post(
            invoice.urls["update"],
            {
                "contact": project.contact_id,
                "title": project.title,
                "description": "bla",
                "owned_by": project.owned_by_id,
                "discount": 0,
                "liable_to_vat": 1,
                "postal_address": "Anything\nStreet\nCity",
                "subtotal": 2500,
                "third_party_costs": 0,
                "apply_down_payment": [],
                "status": Invoice.IN_PREPARATION,
            },
        )
        self.assertRedirects(response, invoice.urls["detail"])

        invoice.refresh_from_db()
        self.assertAlmostEqual(invoice.subtotal, 2500)
        self.assertAlmostEqual(invoice.total_excl_tax, 2500)
        self.assertEqual(invoice.down_payment_applied_to, None)

        down_payment.down_payment_applied_to = invoice
        down_payment.save(update_fields=["down_payment_applied_to"])
        invoice.save()

        response = self.client.post(invoice.urls["delete"])
        self.assertContains(response, "release-down-payments")

        response = self.client.post(
            invoice.urls["delete"],
            {WarningsForm.ignore_warnings_id: "release-down-payments"},
        )
        self.assertRedirects(response, invoice.urls["list"])

    def test_change_contact(self):
        invoice = factories.InvoiceFactory.create(title="Test", subtotal=20)
        self.client.force_login(invoice.owned_by)

        response = self.client.post(
            invoice.urls["update"],
            invoice_to_dict(invoice, contact=factories.PersonFactory.create().pk),
        )
        # print(response.content.decode("utf-8"))
        self.assertContains(
            response,
            "The contact Vorname Nachname does not belong to The Organization Ltd.",
        )

    def test_status(self):
        today = dt.date.today()
        yesterday = dt.date.today() - dt.timedelta(days=1)
        fmt = local_date_format(today)
        self.assertEqual(
            Invoice(status=Invoice.IN_PREPARATION).pretty_status,
            "In preparation since {}".format(fmt),
        )
        self.assertEqual(
            Invoice(status=Invoice.SENT, invoiced_on=today).pretty_status,
            "Sent on {}".format(fmt),
        )
        self.assertEqual(
            Invoice(
                status=Invoice.SENT,
                invoiced_on=yesterday,
                due_on=today - dt.timedelta(days=5),
            ).pretty_status,
            "Sent on {} but overdue".format(local_date_format(yesterday)),
        )
        self.assertIn(
            "badge-warning",
            Invoice(
                status=Invoice.SENT,
                invoiced_on=yesterday,
                due_on=today - dt.timedelta(days=5),
            ).status_badge,
        )
        self.assertEqual(
            Invoice(
                status=Invoice.SENT, invoiced_on=yesterday, last_reminded_on=today
            ).pretty_status,
            "Sent on {}, reminded on {}".format(local_date_format(yesterday), fmt),
        )
        self.assertEqual(
            Invoice(status=Invoice.PAID, closed_on=today).pretty_status,
            "Paid on {}".format(fmt),
        )
        self.assertEqual(Invoice(status=Invoice.CANCELED).pretty_status, "Canceled")

    def test_service_update(self):
        project = factories.ProjectFactory.create()
        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )

        service = invoice.services.create(title="Test", cost=50)

        self.client.force_login(project.owned_by)
        response = self.client.get(service.urls["update"])
        self.assertRedirects(response, invoice.urls["detail"])

        response = self.client.get(
            service.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)

        invoice.status = Invoice.SENT
        invoice.save()

        response = self.client.get(
            service.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Cannot modify a service bound to an invoice which is not in"
            " preparation anymore.",
        )

    def test_person_invoice_without_vat(self):
        # Test another branch in workbench/tools/pdf.py

        invoice = factories.InvoiceFactory.create(liable_to_vat=False)
        self.client.force_login(invoice.owned_by)
        response = self.client.get(invoice.urls["pdf"])
        self.assertEqual(response.status_code, 200)

    def test_cancellation_with_payment_notice(self):
        invoice = factories.InvoiceFactory.create(
            invoiced_on=dt.date.today(),
            due_on=dt.date.today(),
            postal_address="Test\nStreet\nCity",
            status=Invoice.CANCELED,
        )

        msg = [
            (
                "payment_notice",
                ["Please provide a short reason for the invoice cancellation."],
            )
        ]

        with self.assertRaises(ValidationError) as cm:
            invoice.clean_fields()
        self.assertEqual(list(cm.exception), msg)
