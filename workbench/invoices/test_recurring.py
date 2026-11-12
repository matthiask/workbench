import datetime as dt
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench import factories
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.invoices.tasks import create_recurring_invoices_and_notify
from workbench.reporting.models import FreezeDate
from workbench.tools.formats import currency, local_date_format
from workbench.tools.models import default_tax_rate
from workbench.tools.testing import check_code, messages
from workbench.tools.validation import in_days


class RecurringTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_recurring_invoice(self):
        """Creating recurring invoices and invoices from a RI works as expected"""
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

        with travel("2019-01-01 12:00"):
            self.assertEqual(len(ri.create_invoices()), 12)

        ri.ends_on = None
        ri.save()

        with travel("2019-01-01 12:00"):
            self.assertEqual(len(ri.create_invoices()), 1)

        # Continue generating invoices after January '19
        invoices = []
        for ri in RecurringInvoice.objects.renewal_candidates():
            invoices.extend(ri.create_invoices())
        self.assertTrue(len(invoices) > 1)
        self.assertEqual({invoice.type for invoice in invoices}, {Invoice.FIXED})

    def test_creation(self):
        """Creation of recurring invoices, with the customer/contaact pre-form"""
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )

        self.client.force_login(person.primary_contact)

        response = self.client.get("/recurring-invoices/create/")
        self.assertNotContains(response, 'name="title"')

        response = self.client.get(f"/recurring-invoices/create/?contact={person.pk}")
        self.assertContains(
            response,
            # No value!
            '<input type="number" name="third_party_costs" step="0.01" class="form-control" required aria-describedby="id_third_party_costs_helptext" id="id_third_party_costs">',
            html=True,
        )
        # print(response, response.content.decode("utf-8"))

        response = self.client.post(
            f"/recurring-invoices/create/?contact={person.pk}",
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
                "liable_to_vat": "1",
                "third_party_costs": 0,
                "new_invoices": "prepare",
            },
        )
        self.assertContains(response, "No contact selected.")

        response = self.client.post(
            f"/recurring-invoices/create/?contact={person.pk}",
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
                "liable_to_vat": "1",
                "third_party_costs": 0,
                "new_invoices": "prepare",
                "postal_address": "Anything",
            },
        )
        self.assertContains(response, 'value="short-postal-address"')

        response = self.client.post(
            f"/recurring-invoices/create/?contact={person.pk}",
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
                "liable_to_vat": "1",
                "third_party_costs": 0,
                "new_invoices": "prepare",
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

    def test_reactivation_backlog(self):
        """Reactivating a recurring invoice which has ended warns about the
        invoices of the past periods it would create"""
        ri = factories.RecurringInvoiceFactory.create(
            starts_on=dt.date(2025, 1, 1),
            ends_on=dt.date(2025, 3, 31),
            periodicity="monthly",
            subtotal=100,
            postal_address="Name\nStreet\nCity",
        )
        with travel("2025-04-01 12:00"):
            self.assertEqual(len(ri.create_invoices()), 3)
        self.client.force_login(ri.owned_by)

        data = {
            "customer": ri.customer_id,
            "contact": ri.contact_id,
            "title": ri.title,
            "owned_by": ri.owned_by_id,
            "postal_address": ri.postal_address,
            "starts_on": ri.starts_on.isoformat(),
            "ends_on": "",
            "periodicity": "monthly",
            "create_invoice_on_day": -20,
            "subtotal": 100,
            "discount": 0,
            "liable_to_vat": "1",
            "third_party_costs": 0,
            "new_invoices": "prepare",
        }
        with travel("2025-07-15 12:00"):
            response = self.client.post(ri.urls["update"], data)
            self.assertContains(response, "recurring-invoice-backlog")
            self.assertContains(response, "5 invoices for the periods since")

            # Extending it to the current period is fine
            response = self.client.post(
                ri.urls["update"], data | {"ends_on": "2025-04-30"}
            )
            self.assertRedirects(response, ri.urls["detail"])

    def test_create_and_notify(self):
        """The recurring invoices task notifies owners"""
        factories.RecurringInvoiceFactory.create()

        create_recurring_invoices_and_notify()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "recurring invoices")

        create_recurring_invoices_and_notify()
        self.assertEqual(len(mail.outbox), 1)

    def test_list(self):
        """Filter form smoke test"""
        factories.RecurringInvoiceFactory.create()

        user = factories.UserFactory.create()
        self.client.force_login(user)

        code = check_code(self, "/recurring-invoices/")
        code("")
        code("q=test")
        code("s=all")
        code("s=closed")
        code(f"org={factories.OrganizationFactory.create().pk}")
        code(f"owned_by={user.id}")
        code("owned_by=-1")  # mine
        code("owned_by=0")  # only inactive

    def test_pretty_status(self):
        """Recurring invoice status badge"""
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
        self.assertEqual(
            ri.pretty_next_period,
            "Next period starts on 01.01.2018, invoice will be created on 12.12.2017",
        )

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
        self.assertEqual(
            ri.pretty_next_period,
            "Next period starts on 01.01.2018, invoice will be created on 12.12.2017",
        )

        ri = RecurringInvoice.objects.create(
            customer=person.organization,
            contact=person,
            title="Recurring invoice",
            owned_by=person.primary_contact,
            starts_on=dt.date(2018, 1, 1),
            ends_on=dt.date(2018, 1, 31),
            next_period_starts_on=dt.date(2018, 2, 1),
            periodicity="monthly",
            subtotal=200,
        )
        self.assertEqual(ri.pretty_status, "monthly from 01.01.2018 until 31.01.2018")
        self.assertEqual(ri.pretty_next_period, "")

    def test_pre_form(self):
        """Pre-form branch coverage"""
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
            RecurringInvoice.urls["create"] + f"?customer={organization.pk}"
        )
        self.assertContains(response, 'method="POST"')

        person = factories.PersonFactory.create()
        response = self.client.get(
            RecurringInvoice.urls["create"] + f"?contact={person.pk}"
        )
        self.assertContains(response, 'method="POST"')

    def test_copy(self):
        """Copying recurring invoices"""
        invoice = factories.RecurringInvoiceFactory.create()
        self.client.force_login(invoice.owned_by)

        response = self.client.get(invoice.urls["create"] + "?copy=" + str(invoice.pk))
        self.assertContains(response, f'value="{invoice.title}"')
        # print(response, response.content.decode("utf-8"))

        response = self.client.get(invoice.urls["create"] + "?copy=blub")
        self.assertEqual(response.status_code, 200)  # No crash

    def test_renewal_candidates(self):
        """Renewal candidates depends on start date and the day of period when
        the invoice is created"""
        r1 = factories.RecurringInvoiceFactory.create(
            starts_on=in_days(10),
            periodicity="monthly",
        )
        r2 = factories.RecurringInvoiceFactory.create(
            starts_on=in_days(30),
            periodicity="monthly",
        )

        self.assertEqual(set(RecurringInvoice.objects.renewal_candidates()), {r1})

        r3 = factories.RecurringInvoiceFactory.create(
            starts_on=in_days(-250),
            periodicity="yearly",
            create_invoice_on_day=300,
        )
        r4 = factories.RecurringInvoiceFactory.create(
            starts_on=in_days(-350),
            periodicity="yearly",
            create_invoice_on_day=300,
        )

        self.assertEqual(set(RecurringInvoice.objects.renewal_candidates()), {r1, r4})

        _ = r2, r3

    def test_positive_create_invoice_on_day(self):
        """Invoice creation can be moved within the period"""
        r1 = factories.RecurringInvoiceFactory.create(
            starts_on=dt.date.today(),
            periodicity="monthly",
        )
        r2 = factories.RecurringInvoiceFactory.create(
            starts_on=dt.date.today(),
            periodicity="monthly",
            # Wait with invoice creation until 10 days into the period:
            create_invoice_on_day=10,
        )

        self.assertEqual(len(r1.create_invoices()), 1)
        self.assertEqual(len(r2.create_invoices()), 0)

    def test_create_project(self):
        """Recurring invoices may optionally create projects"""
        r = factories.RecurringInvoiceFactory.create(create_project=True)

        invoices = r.create_invoices()
        self.assertIsNotNone(invoices[0].project)
        self.assertEqual(invoices[0].type, invoices[0].DOWN_PAYMENT)

    def test_mark_as_sent(self):
        """Recurring invoices may optionally create sent invoices; invoice
        dates in the frozen period move to the day after the freeze date, also
        for invoices in preparation"""
        r = factories.RecurringInvoiceFactory.create(
            starts_on=in_days(-70),
            periodicity="monthly",
            create_invoice_on_day=0,
            subtotal=100,
            postal_address="Name\nStreet\nCity",
        )
        self.assertEqual(r.new_invoices, RecurringInvoice.PREPARE)
        FreezeDate.objects.create(up_to=in_days(-50))
        [invoice, *_rest] = r.create_invoices()
        self.assertEqual(invoice.status, Invoice.IN_PREPARATION)
        self.assertEqual(invoice.invoiced_on, in_days(-49))
        self.assertEqual(invoice.service_period_from, in_days(-70))
        Invoice.objects.all().delete()

        r.new_invoices = RecurringInvoice.MARK_AS_SENT
        r.next_period_starts_on = None
        r.save()
        invoices = r.create_invoices()
        self.assertEqual(
            [invoice.status for invoice in invoices],
            [Invoice.SENT, Invoice.SENT, Invoice.SENT],
        )
        self.assertEqual(invoices[0].invoiced_on, in_days(-49))
        self.assertEqual(invoices[0].due_on, in_days(-49 + 15))
        self.assertEqual(invoices[0].service_period_from, in_days(-70))

    def test_send_automatically(self):
        """Recurring invoices may send their invoices to the first suggested
        address; frozen invoice dates move to the day after the freeze date"""
        r = factories.RecurringInvoiceFactory.create(
            starts_on=in_days(-70),
            periodicity="monthly",
            create_invoice_on_day=0,
            subtotal=100,
            postal_address="Name\nStreet\nCity",
            new_invoices="send",
        )
        FreezeDate.objects.create(up_to=in_days(-50))

        # Without an address nothing is sent
        invoices = r.create_invoices()
        self.assertEqual(
            {invoice.status for invoice in invoices}, {Invoice.IN_PREPARATION}
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(
            [invoice.sending for invoice in invoices],
            ["Not sent: No email address."] * 3,
        )

        Invoice.objects.all().delete()
        r.contact.emailaddresses.create(email="contact@example.com")
        r.next_period_starts_on = None
        r.save()
        invoices = r.create_invoices()
        self.assertEqual({invoice.status for invoice in invoices}, {Invoice.SENT})
        self.assertEqual(invoices[1].sending, "Sent to contact@example.com")
        self.assertEqual(len(mail.outbox), 3)
        invoices[0].refresh_from_db()
        self.assertEqual(invoices[0].invoiced_on, in_days(-49))
        self.assertEqual(invoices[0].due_on, in_days(-49 + 15))
        self.assertEqual(invoices[0].service_period_from, in_days(-70))
        message = mail.outbox[1]
        self.assertEqual(message.to, ["contact@example.com"])
        self.assertEqual(message.cc, [r.owned_by.email])
        self.assertEqual(message.reply_to, [r.owned_by.email])
        self.assertIn(invoices[1].code, message.subject)
        self.assertIn(local_date_format(invoices[1].due_on), message.body)
        self.assertEqual(len(message.attachments), 1)

    def test_send_automatically_configured(self):
        """The recipient, subject and text are configured on the recurring
        invoice; the placeholders are replaced for each invoice"""
        r = factories.RecurringInvoiceFactory.create(
            subtotal=100,
            postal_address="Name\nStreet\nCity",
            new_invoices="send",
            send_to="other@example.com",
            mail_subject="Rechnung {code}",
            mail_body="{total} für {service_period}, bis {due_on}.",
        )
        r.contact.emailaddresses.create(email="contact@example.com")
        [invoice] = r.create_invoices()
        self.assertEqual(invoice.status, Invoice.SENT)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["other@example.com"])
        self.assertEqual(message.subject, f"Rechnung {invoice.code}")
        self.assertEqual(
            message.body,
            f"{currency(invoice.total)} für {invoice.service_period},"
            f" bis {local_date_format(invoice.due_on)}.",
        )

    def test_send_automatically_form(self):
        """The form proposes the recipient and the mail with placeholders"""
        r = factories.RecurringInvoiceFactory.create(
            subtotal=100,
            postal_address="Name\nStreet\nCity",
            starts_on=in_days(10),
        )
        r.contact.salutation = "Liebe Anna"
        r.contact.address_on_first_name_terms = True
        r.contact.save()
        r.contact.emailaddresses.create(email="anna@example.com")
        self.client.force_login(r.owned_by)

        response = self.client.get(r.urls["update"])
        self.assertContains(response, 'value="anna@example.com"')
        self.assertContains(response, "Rechnung {code} von")
        self.assertContains(response, "Liebe Anna")
        self.assertContains(response, "über CHF {total}, zahlbar bis {due_on}")

        data = {
            "customer": r.customer_id,
            "contact": r.contact_id,
            "title": r.title,
            "owned_by": r.owned_by_id,
            "postal_address": r.postal_address,
            "starts_on": r.starts_on.isoformat(),
            "periodicity": "yearly",
            "create_invoice_on_day": -20,
            "subtotal": 100,
            "discount": 0,
            "liable_to_vat": "1",
            "third_party_costs": 0,
            "new_invoices": "send",
        }
        response = self.client.post(r.urls["update"], data)
        self.assertRedirects(response, r.urls["detail"])
        r.refresh_from_db()
        self.assertEqual(r.send_to, "anna@example.com")
        self.assertContains(self.client.get(r.urls["detail"]), "anna@example.com")
        self.assertIn("{code}", r.mail_subject)
        self.assertIn("Liebe Anna", r.mail_body)

        # Without any address
        r.contact.emailaddresses.all().delete()
        response = self.client.post(r.urls["update"], data | {"send_to": ""})
        self.assertContains(response, "No email address.")

    def test_send_automatically_manually(self):
        """Creating the invoices by hand shows what has been sent"""
        r = factories.RecurringInvoiceFactory.create(
            subtotal=100, postal_address="Name\nStreet\nCity", new_invoices="send"
        )
        r.contact.emailaddresses.create(email="contact@example.com")
        self.client.force_login(r.owned_by)
        response = self.client.get(r.get_absolute_url() + "?create_invoices=1")
        invoice = Invoice.objects.get()
        self.assertEqual(
            messages(response),
            ["Created 1 invoice.", f"{invoice}: Sent to contact@example.com"],
        )

    def test_send_automatically_notification(self):
        """The owners' mail says whether new invoices have been sent"""
        r = factories.RecurringInvoiceFactory.create(
            subtotal=100, postal_address="Name\nStreet\nCity", new_invoices="send"
        )
        r.contact.emailaddresses.create(email="contact@example.com")
        create_recurring_invoices_and_notify()
        self.assertEqual(
            [message.subject for message in mail.outbox][-1], "recurring invoices"
        )
        self.assertIn("Sent to contact@example.com", mail.outbox[-1].body)

    def test_current_tax_rate(self):
        """Recurring invoices have no tax rate of their own, they and their
        invoices use the current one"""
        self.assertNotIn(
            "tax_rate", {field.name for field in RecurringInvoice._meta.get_fields()}
        )
        ri = factories.RecurringInvoiceFactory.create(subtotal=100)
        self.assertEqual(ri.tax_rate, default_tax_rate())
        self.assertEqual(ri.total, Decimal("108.10"))
