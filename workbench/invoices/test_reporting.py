import datetime as dt

from django.test import TestCase

from workbench import factories
from workbench.tools.testing import messages


class ReportingTest(TestCase):
    def test_open_items(self):
        for i in range(20):
            factories.InvoiceFactory.create(
                invoiced_on=dt.date.today(),
                due_on=dt.date.today() + dt.timedelta(days=15),
                subtotal=50,
                status=factories.Invoice.SENT,
            )

        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/report/open-items-list/?cutoff_date=bla")
        self.assertRedirects(response, "/report/open-items-list/")
        self.assertEqual(messages(response), ["Form was invalid."])
        response = self.client.get("/report/open-items-list/")
        self.assertContains(response, '<th class="text-right">1’000.00</th>')

        response = self.client.get(
            "/report/open-items-list/?cutoff_date={}".format(
                (dt.date.today() - dt.timedelta(days=1)).isoformat()
            )
        )
        self.assertContains(response, '<th class="text-right">0.00</th>')

        self.assertEqual(
            self.client.get("/report/open-items-list/?xlsx=1").status_code, 200
        )
        # print(response, response.content.decode("utf-8"))

        self.assertEqual(self.client.get("/report/key-data/").status_code, 200)

    def test_monthly_invoicing_form(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/report/monthly-invoicing/")
        self.assertContains(response, "monthly invoicing")

        response = self.client.get("/report/monthly-invoicing/?year=2018")
        self.assertContains(response, "monthly invoicing")

        response = self.client.get("/report/monthly-invoicing/?year=bla")
        self.assertRedirects(response, "/report/monthly-invoicing/")
        self.assertEqual(messages(response), [])
