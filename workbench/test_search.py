from django.test import TestCase

from workbench import factories


class SearchTest(TestCase):
    def test_search(self):
        project = factories.ProjectFactory.create(title="Test")
        self.client.force_login(project.owned_by)

        response = self.client.get("/search/")
        self.assertContains(response, "Suchanfrage fehlt.")

        response = self.client.get("/search/?q=Test")
        self.assertContains(response, project.get_absolute_url())
