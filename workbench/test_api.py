from django.test import TestCase

from workbench import factories


class APITest(TestCase):
    def test_openapi_schema(self):
        """The API describes itself, but only to authenticated users"""
        response = self.client.get("/api/openapi.json")
        self.assertEqual(response.status_code, 302)

        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/api/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["info"]["title"], "Workbench")
