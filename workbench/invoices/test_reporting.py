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
        for _i in range(5):
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
        self.assertContains(response, '<div class="wb-stat-value">300.00</div>')
        # Nothing overdue, all due in the week in 15 days
        [overdue, *weeks] = response.context["chart"]["columns"]
        self.assertEqual(overdue["title"], "overdue\noverdue: 0.00")
        self.assertIn("due: 300.00", weeks[-1]["title"])

        response = self.client.get(
            f"/report/open-items-list/?cutoff_date={in_days(-1).isoformat()}"
        )
        self.assertContains(response, '<div class="wb-stat-value">0.00</div>')

        self.assertEqual(
            self.client.get("/report/open-items-list/?export=xlsx").status_code, 200
        )
        # print(response, response.content.decode("utf-8"))

        factories.InvoiceFactory.create(
            invoiced_on=in_days(-40),
            due_on=in_days(-1),
            subtotal=20,
            status=factories.Invoice.SENT,
        )
        response = self.client.get("/report/open-items-list/")
        self.assertIn(
            "overdue: 20.00", response.context["chart"]["columns"][0]["title"]
        )

        # Hit the key data view to cover some branches and verify that it does not crash
        self.assertEqual(self.client.get("/report/key-data/").status_code, 200)
