from datetime import date
from decimal import Decimal

from django.core import mail
from django.test import TestCase

from workbench import factories
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.invoices.reporting import monthly_invoicing
from workbench.invoices.tasks import create_recurring_invoices_and_notify
from workbench.tools.formats import local_date_format
from workbench.tools.testing import messages


class RecurringTest(TestCase):
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
            starts_on=date(2018, 1, 1),
            ends_on=date(2018, 12, 31),
            periodicity="monthly",
            subtotal=200,
        )

        self.assertEqual(ri.next_period_starts_on, None)

        self.assertEqual(len(ri.create_invoices(generate_until=date(2019, 1, 1))), 12)

        ri.ends_on = None
        ri.save()
        self.assertEqual(len(ri.create_invoices(generate_until=date(2019, 1, 1))), 1)

        # Not so clean, but we have a few invoices here...
        mi = monthly_invoicing(2018)
        self.assertAlmostEqual(mi["third_party_costs"], Decimal(0))
        self.assertAlmostEqual(mi["total"], Decimal(200 * 12) * Decimal("1.077"))
        self.assertAlmostEqual(mi["total_excl_tax"], Decimal(200 * 12))

        self.assertEqual(
            [month["total_excl_tax"] for month in mi["months"]],
            [Decimal("200.00") for i in range(12)],
        )

        mi = monthly_invoicing(2019)
        self.assertAlmostEqual(mi["third_party_costs"], Decimal(0))
        self.assertAlmostEqual(mi["total"], Decimal(200) * Decimal("1.077"))
        self.assertAlmostEqual(mi["total_excl_tax"], Decimal(200))

        self.assertEqual(
            [month["total_excl_tax"] for month in mi["months"]], [Decimal("200.00")]
        )

        # Continue generating invoices after January '19
        self.assertTrue(len(RecurringInvoice.objects.create_invoices()) > 1)

    def test_creation(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )

        self.client.force_login(person.primary_contact)

        response = self.client.post(
            "/recurring-invoices/create/",
            {
                "customer": person.organization_id,
                # "contact": person.id,
                "title": "recur",
                "owned_by": person.primary_contact_id,
                "starts_on": local_date_format(date.today()),
                "periodicity": "yearly",
                "subtotal": 500,
                "discount": 0,
                "liable_to_vat": "on",
                "third_party_costs": 0,
            },
        )
        self.assertContains(response, "Kein Kontakt ausgewählt.")

        response = self.client.post(
            "/recurring-invoices/create/",
            {
                "customer": person.organization_id,
                "contact": person.id,
                "title": "recur",
                "owned_by": person.primary_contact_id,
                "starts_on": local_date_format(date.today()),
                "periodicity": "yearly",
                "subtotal": 500,
                "discount": 0,
                "liable_to_vat": "on",
                "third_party_costs": 0,
            },
        )

        ri = RecurringInvoice.objects.get()
        self.assertRedirects(response, ri.urls["update"])

        factories.PostalAddressFactory.create(person=person)
        response = self.client.get(ri.urls["update"])
        self.assertContains(response, 'name="pa"')
        self.assertNotContains(response, 'name="postal_address"')

        response = self.client.get(ri.urls["detail"])
        self.assertContains(response, "?create_invoices=1")

        response = self.client.get(ri.urls["detail"] + "?create_invoices=1")
        self.assertRedirects(response, Invoice().urls["list"])
        self.assertEqual(messages(response), ["1 Rechnung erstellt."])

        response = self.client.get(ri.urls["detail"] + "?create_invoices=1")
        self.assertRedirects(response, ri.urls["detail"])
        self.assertEqual(messages(response), ["0 Rechnungen erstellt."])

    def test_create_and_notify(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        RecurringInvoice.objects.create(
            customer=person.organization,
            contact=person,
            title="Recurring invoice",
            description="",
            owned_by=person.primary_contact,
            starts_on=date(2018, 1, 1),
            ends_on=date(2018, 12, 31),
            periodicity="monthly",
            subtotal=200,
        )

        create_recurring_invoices_and_notify()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Stapelrechnungen")

        create_recurring_invoices_and_notify()
        self.assertEqual(len(mail.outbox), 1)

    def test_list(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def valid(p):
            self.assertEqual(
                self.client.get("/recurring-invoices/?" + p).status_code, 200
            )

        valid("")
        valid("s=all")
        valid("s=closed")
        valid("org={}".format(factories.OrganizationFactory.create().pk))
        valid("owned_by={}".format(user.id))
        valid("owned_by=0")  # only inactive

    def test_pretty_periodicity(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )

        ri = RecurringInvoice.objects.create(
            customer=person.organization,
            contact=person,
            title="Recurring invoice",
            owned_by=person.primary_contact,
            starts_on=date(2018, 1, 1),
            ends_on=date(2050, 12, 31),
            periodicity="monthly",
            subtotal=200,
        )
        self.assertEqual(
            ri.pretty_periodicity, "monatlich von 01.01.2018 bis 31.12.2050"
        )

        ri = RecurringInvoice.objects.create(
            customer=person.organization,
            contact=person,
            title="Recurring invoice",
            owned_by=person.primary_contact,
            starts_on=date(2018, 1, 1),
            ends_on=None,
            periodicity="monthly",
            subtotal=200,
        )
        self.assertEqual(ri.pretty_periodicity, "monatlich seit 01.01.2018")
