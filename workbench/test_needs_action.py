from django.test import TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.views import NEEDS_ACTION_SHOWN


class NeedsActionTest(TestCase):
    @override_settings(FEATURES={FEATURES.DEALS: F.ALWAYS})
    def test_long_categories(self):
        """Long categories show their first entries, the others on request"""
        user = factories.UserFactory.create()
        deals = [
            factories.DealFactory.create(owned_by=user, title=f"Deal {i}")
            for i in range(NEEDS_ACTION_SHOWN + 2)
        ]
        self.client.force_login(user)

        response = self.client.get("/")
        self.assertContains(response, "Show 2 more")
        self.assertContains(response, "wb-needs-action-more", count=2)
        for deal in deals:
            self.assertContains(response, deal.get_absolute_url())

        # "Show 1 more" would take as much space as the entry itself
        deals[0].delete()
        response = self.client.get("/")
        self.assertNotContains(response, "wb-needs-action-more")
        self.assertContains(response, deals[-1].get_absolute_url())
