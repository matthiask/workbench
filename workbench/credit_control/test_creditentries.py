from django.test import TestCase

from workbench import factories
from workbench.tools.testing import messages


class CreditEntriesTest(TestCase):
    def test_assignment(self):
        for i in range(10):
            invoice = factories.InvoiceFactory.create(
                subtotal=10 + i, liable_to_vat=False
            )

        entry_0 = factories.CreditEntryFactory.create(total=12)
        entry_1 = factories.CreditEntryFactory.create(total=14)
        entry_2 = factories.CreditEntryFactory.create(total=19)

        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/credit-control/assign/")
        # print(response, response.content.decode("utf-8"))

        self.assertContains(response, "widget--radioselect", 3)
        response = self.client.post(
            "/credit-control/assign/",
            {
                "entry_{}_invoice".format(entry_2.pk): invoice.pk,
                "entry_{}_notes".format(entry_1.pk): "Stuff",
            },
        )
        self.assertRedirects(response, "/credit-control/assign/")

        response = self.client.get("/credit-control/assign/")
        self.assertContains(response, "widget--radioselect", 1)

        response = self.client.post(
            "/credit-control/assign/",
            {"entry_{}_notes".format(entry_0.pk): "Stuff"},
            follow=True,
        )
        self.assertRedirects(response, "/credit-control/")
        self.assertEqual(
            messages(response),
            [
                "Gutschriften wurden erfolgreich geändert.",
                "All credit entries have already been assigned.",
            ],
        )
