import datetime as dt

from django.core import mail
from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.invoices.tasks import create_recurring_invoices_and_notify
from workbench.tools.testing import check_code, messages


class RecurringTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_recurring_invoice(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        pa = factories.PostalAddressFactory.create(person=person)

        ri = RecurringInvoice.objects.create(
            customer=person.organization,
            contact=person,
            title="Recurring invoice",
            description="",
            owned_by=person.primary_contact,
            postal_address=pa.postal_address,
            starts_on=dt.date(2018, 1, 1),
            ends_on=dt.date(2018, 12, 31),
            periodicity="monthly",
            subtotal=200,
        )

        self.assertEqual(ri.next_period_starts_on, None)

        self.assertEqual(
            len(ri.create_invoices(generate_until=dt.date(2019, 1, 1))), 12
        )

        ri.ends_on = None
        ri.save()
        self.assertEqual(len(ri.create_invoices(generate_until=dt.date(2019, 1, 1))), 1)

        # Continue generating invoices after January '19
        self.assertTrue(len(RecurringInvoice.objects.create_invoices()) > 1)

    def test_creation(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )

        self.client.force_login(person.primary_contact)

        response = self.client.get("/recurring-invoices/create/")
        self.assertNotContains(response, 'name="title"')

        response = self.client.get(
            "/recurring-invoices/create/?contact={}".format(person.pk)
        )
        self.assertContains(
            response,
            # No value!
            '<input type="number" name="third_party_costs" step="0.01" class="form-control" required id="id_third_party_costs">',  # noqa
            html=True,
        )
        # print(response, response.content.decode("utf-8"))

        response = self.client.post(
            "/recurring-invoices/create/?contact={}".format(person.pk),
            {
                "customer": person.organization_id,
                # "contact": person.id,
                "title": "recur",
                "owned_by": person.primary_contact_id,
                "starts_on": dt.date.today().isoformat(),
                "periodicity": "yearly",
                "create_invoice_on_day": -20,
                "subtotal": 500,
                "discount": 0,
                "liable_to_vat": "on",
                "third_party_costs": 0,
            },
        )
        self.assertContains(response, "No contact selected.")

        response = self.client.post(
            "/recurring-invoices/create/?contact={}".format(person.pk),
            {
                "customer": person.organization_id,
                "contact": person.id,
                "title": "recur",
                "owned_by": person.primary_contact_id,
                "starts_on": dt.date.today().isoformat(),
                "periodicity": "yearly",
                "create_invoice_on_day": -20,
                "subtotal": 500,
                "discount": 0,
                "liable_to_vat": "on",
                "third_party_costs": 0,
                "postal_address": "Anything",
            },
        )
        self.assertContains(response, 'value="short-postal-address"')

        response = self.client.post(
            "/recurring-invoices/create/?contact={}".format(person.pk),
            {
                "customer": person.organization_id,
                "contact": person.id,
                "title": "recur",
                "owned_by": person.primary_contact_id,
                "starts_on": dt.date.today().isoformat(),
                "periodicity": "yearly",
                "create_invoice_on_day": -20,
                "subtotal": 500,
                "discount": 0,
                "liable_to_vat": "on",
                "third_party_costs": 0,
                "postal_address": "Anything\nStreet\nCity",
            },
        )

        ri = RecurringInvoice.objects.get()
        self.assertRedirects(response, ri.urls["detail"])

        factories.PostalAddressFactory.create(person=person)
        response = self.client.get(ri.urls["update"])
        self.assertContains(response, 'name="postal_address"')
        self.assertContains(response, 'data-field-value="')

        response = self.client.get(ri.urls["detail"])
        self.assertContains(response, "?create_invoices=1")

        response = self.client.get(ri.urls["detail"] + "?create_invoices=1")
        self.assertRedirects(response, Invoice.urls["list"])
        self.assertEqual(messages(response), ["Created 1 invoice."])

        response = self.client.get(ri.urls["detail"] + "?create_invoices=1")
        self.assertRedirects(response, ri.urls["detail"])
        self.assertEqual(messages(response), ["Created 0 invoices."])

    def test_create_and_notify(self):
        factories.RecurringInvoiceFactory.create()

        create_recurring_invoices_and_notify()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "recurring invoices")

        create_recurring_invoices_and_notify()
        self.assertEqual(len(mail.outbox), 1)

    def test_list(self):
        factories.RecurringInvoiceFactory.create()

        user = factories.UserFactory.create()
        self.client.force_login(user)

        code = check_code(self, "/recurring-invoices/")
        code("")
        code("q=test")
        code("s=all")
        code("s=closed")
        code("org={}".format(factories.OrganizationFactory.create().pk))
        code("owned_by={}".format(user.id))
        code("owned_by=-1")  # mine
        code("owned_by=0")  # only inactive

    def test_pretty_status(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )

        ri = RecurringInvoice.objects.create(
            customer=person.organization,
            contact=person,
            title="Recurring invoice",
            owned_by=person.primary_contact,
            starts_on=dt.date(2018, 1, 1),
            ends_on=dt.date(2050, 12, 31),
            periodicity="monthly",
            subtotal=200,
        )
        self.assertEqual(ri.pretty_status, "monthly from 01.01.2018 until 31.12.2050")

        ri = RecurringInvoice.objects.create(
            customer=person.organization,
            contact=person,
            title="Recurring invoice",
            owned_by=person.primary_contact,
            starts_on=dt.date(2018, 1, 1),
            ends_on=None,
            periodicity="monthly",
            subtotal=200,
        )
        self.assertEqual(ri.pretty_status, "monthly from 01.01.2018")

    def test_pre_form(self):
        self.client.force_login(factories.UserFactory.create())

        # pre_form does not have these fields
        response = self.client.get(RecurringInvoice.urls["create"])
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        # Nonexistant entries
        response = self.client.get(RecurringInvoice.urls["create"] + "?contact=0")
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        response = self.client.get(RecurringInvoice.urls["create"] + "?customer=0")
        self.assertContains(response, 'method="GET"')
        self.assertNotContains(response, 'id="id_title"')
        self.assertNotContains(response, 'id="id_description"')

        # Existing
        organization = factories.OrganizationFactory.create()
        response = self.client.get(
            RecurringInvoice.urls["create"] + "?customer={}".format(organization.pk)
        )
        self.assertContains(response, 'method="POST"')

        person = factories.PersonFactory.create()
        response = self.client.get(
            RecurringInvoice.urls["create"] + "?contact={}".format(person.pk)
        )
        self.assertContains(response, 'method="POST"')

    def test_copy(self):
        invoice = factories.RecurringInvoiceFactory.create()
        self.client.force_login(invoice.owned_by)

        response = self.client.get(invoice.urls["create"] + "?copy=" + str(invoice.pk))
        self.assertContains(response, 'value="{}"'.format(invoice.title))
        # print(response, response.content.decode("utf-8"))

        response = self.client.get(invoice.urls["create"] + "?copy=blub")
        self.assertEqual(response.status_code, 200)  # No crash
