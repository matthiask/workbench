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
