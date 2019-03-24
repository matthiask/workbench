from django.test import TestCase

from workbench import factories


class DealsTest(TestCase):
    def test_list(self):
        self.client.force_login(factories.UserFactory.create())

        self.assertEqual(self.client.get("/deals/").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=all").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=10").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=20").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=30").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=40").status_code, 302)

    def test_detail(self):
        deal = factories.DealFactory.create()

        self.client.force_login(deal.owned_by)
        response = self.client.get(deal.urls["detail"])
        # print(response, response.content.decode("utf-8"))

        self.assertContains(response, "Keine Aktivitäten")
        self.assertContains(response, "<td>42.00</td>")
