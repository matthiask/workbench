from django.test import TestCase

from workbench import factories
from workbench.tools.search import process_query


class SearchTest(TestCase):
    def test_search(self):
        project = factories.ProjectFactory.create(title="Test")
        self.client.force_login(project.owned_by)

        response = self.client.get("/search/")
        self.assertContains(response, "Suchanfrage fehlt.")

        response = self.client.get("/search/?q=Test")
        self.assertContains(response, project.get_absolute_url())

    def test_process_query(self):
        self.assertEqual(process_query(""), "")
        self.assertEqual(process_query("org"), "org:*")
        self.assertEqual(process_query("a b"), "a & b:*")
        self.assertEqual(process_query("(foo bar)"), "foo & bar:*")
