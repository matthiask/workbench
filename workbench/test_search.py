from django.test import TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.accounts.features import F
from workbench.tools.search import process_query
from workbench.views import SEARCH_SHOWN


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
        # Types without results are only listed
        for label in [
            "Organizations",
            "People",
            "Invoices",
            "Recurring invoices",
            "Offers",
            "Deals",
        ]:
            self.assertContains(
                response, f'<span class="nav-link disabled">{label}</span>'
            )

        with override_settings(FEATURES={"CONTROLLING": F.NEVER}):
            response = self.client.get("/search/?q=Test")
            self.assertContains(response, project.get_absolute_url())

            self.assertContains(response, "/projects/?q=Test")
            self.assertContains(
                response, '<span class="nav-link disabled">People</span>'
            )
            for label in ["Invoices", "Recurring invoices", "Offers", "Deals"]:
                self.assertNotContains(
                    response, f'<span class="nav-link disabled">{label}</span>'
                )

    def test_deals_require_the_deals_feature(self):
        """Deals are searched with the deals feature, like their views"""
        project = factories.ProjectFactory.create(title="Test")
        self.client.force_login(project.owned_by)
        deals = '<span class="nav-link disabled">Deals</span>'

        with override_settings(FEATURES={"CONTROLLING": F.ALWAYS, "DEALS": F.NEVER}):
            self.assertNotContains(self.client.get("/search/?q=Test"), deals)
        with override_settings(FEATURES={"CONTROLLING": F.NEVER, "DEALS": F.ALWAYS}):
            self.assertContains(self.client.get("/search/?q=Test"), deals)

    def test_search_more(self):
        """Types show a few results right away, the others on request; the
        jump links lead to the types with results"""
        projects = [
            factories.ProjectFactory.create(title=f"Relaunch {i}")
            for i in range(SEARCH_SHOWN + 2)
        ]
        self.client.force_login(projects[0].owned_by)

        response = self.client.get("/search/?q=Relaunch")
        self.assertContains(response, 'href="#search-project"')
        self.assertNotContains(response, 'href="#search-person"')
        self.assertContains(response, 'id="search-project"')
        self.assertContains(response, "Show 2 more")
        self.assertContains(response, "wb-more", count=2)
        for project in projects:
            self.assertContains(response, project.get_absolute_url())
        self.assertNotContains(response, "No results found.")

        response = self.client.get("/search/?q=Nothing")
        self.assertContains(response, "No results found.", count=1)

    def test_process_query(self):
        """Specific testing of query->tsquery conversion"""
        self.assertEqual(process_query(""), "")
        self.assertEqual(process_query("org"), "org:*")
        self.assertEqual(process_query("a b"), "a & b:*")
        self.assertEqual(process_query("(foo bar)"), "foo & bar:*")
