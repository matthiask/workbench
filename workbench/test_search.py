from django.test import TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.tools.search import process_query


class SearchTest(TestCase):
    def test_search(self):
        """Searching works and only shows allowed content objects"""
        project = factories.ProjectFactory.create(title="Test")
        self.client.force_login(project.owned_by)

        response = self.client.get("/search/")
        self.assertContains(response, "Search query missing.")

        response = self.client.get("/search/?q=Test")
        self.assertContains(response, project.get_absolute_url())

        self.assertContains(response, "projects")
        self.assertContains(response, "organizations")
        self.assertContains(response, "people")
        self.assertContains(response, "invoices")
        self.assertContains(response, "recurring-invoices")
        self.assertContains(response, "offers")
        self.assertContains(response, "deals")

        with override_settings(FEATURES={"controlling": False}):
            response = self.client.get("/search/?q=Test")
            self.assertContains(response, project.get_absolute_url())

            self.assertContains(response, "projects")
            self.assertContains(response, "organizations")
            self.assertContains(response, "people")
            self.assertNotContains(response, "invoices")
            self.assertNotContains(response, "recurring-invoices")
            self.assertNotContains(response, "offers")
            self.assertNotContains(response, "deals")

    def test_process_query(self):
        """Specific testing of query->tsquery conversion"""
        self.assertEqual(process_query(""), "")
        self.assertEqual(process_query("org"), "org:*")
        self.assertEqual(process_query("a b"), "a & b:*")
        self.assertEqual(process_query("(foo bar)"), "foo & bar:*")
