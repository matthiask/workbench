from django.test import TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.accounts.features import F
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

        self.assertContains(response, "/projects/?q=Test")
        self.assertContains(response, "/contacts/organizations/?q=Test")
        self.assertContains(response, "/contacts/people/?q=Test")
        self.assertContains(response, "/invoices/?q=Test")
        self.assertContains(response, "/recurring-invoices/?q=Test")
        self.assertContains(response, "/projects/offers/?q=Test")
        self.assertContains(response, "/deals/?q=Test")

        with override_settings(FEATURES={"CONTROLLING": F.NEVER}):
            response = self.client.get("/search/?q=Test")
            self.assertContains(response, project.get_absolute_url())

            self.assertContains(response, "/projects/?q=Test")
            self.assertContains(response, "/contacts/organizations/?q=Test")
            self.assertContains(response, "/contacts/people/?q=Test")
            self.assertNotContains(response, "/invoices/?q=Test")
            self.assertNotContains(response, "/recurring-invoices/?q=Test")
            self.assertNotContains(response, "/projects/offers/?q=Test")
            self.assertNotContains(response, "/deals/?q=Test")

    def test_process_query(self):
        """Specific testing of query->tsquery conversion"""
        self.assertEqual(process_query(""), "")
        self.assertEqual(process_query("org"), "org:*")
        self.assertEqual(process_query("a b"), "a & b:*")
        self.assertEqual(process_query("(foo bar)"), "foo & bar:*")
