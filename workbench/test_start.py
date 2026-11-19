from django.test import TestCase

from workbench import factories


class StartTest(TestCase):
    def test_no_active_projects(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get("/")
        self.assertContains(response, "No active projects")
