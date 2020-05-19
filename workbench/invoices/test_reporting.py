from django.test import TestCase

from workbench import factories
from workbench.tools.testing import messages
from workbench.tools.validation import in_days


class ReportingTest(TestCase):
    def test_open_items(self):
        """The open items list offers filtering by cutoff date and XLSX exports"""
        invoice = factories.InvoiceFactory.create(
            invoiced_on=in_days(0),
            due_on=in_days(15),
            subtotal=50,
            status=factories.Invoice.SENT,
            third_party_costs=5,  # key data branch
        )
        for i in range(5):
            factories.InvoiceFactory.create(
                customer=invoice.customer,
                contact=invoice.contact,
                owned_by=invoice.owned_by,
                invoiced_on=in_days(0),
                due_on=in_days(15),
                subtotal=50,
                status=factories.Invoice.SENT,
                third_party_costs=5,  # key data branch
            )

        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/report/open-items-list/?cutoff_date=bla")
        self.assertRedirects(response, "/report/open-items-list/")
        self.assertEqual(messages(response), ["Form was invalid."])
        response = self.client.get("/report/open-items-list/")
        self.assertContains(response, '<th class="text-right">300.00</th>')

        response = self.client.get(
            "/report/open-items-list/?cutoff_date={}".format(in_days(-1).isoformat())
        )
        self.assertContains(response, '<th class="text-right">0.00</th>')

        self.assertEqual(
            self.client.get("/report/open-items-list/?export=xlsx").status_code, 200
        )
        # print(response, response.content.decode("utf-8"))

        # Hit the key data view to cover some branches and verify that it does not crash
        self.assertEqual(self.client.get("/report/key-data/").status_code, 200)
