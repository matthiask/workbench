from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.tools.validation import monday


class OverviewAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_overview(self):
        """What's on the user's plate"""
        user = factories.UserFactory.create()
        project = factories.ProjectFactory.create(owned_by=user)
        factories.ProjectFactory.create()  # Someone else's
        offer = factories.OfferFactory.create(project=project, owned_by=user)
        factories.PlannedWorkFactory.create(
            project=project, user=user, weeks=[monday()], planned_hours=8
        )
        deal = factories.DealFactory.create(owned_by=user)
        self.client.force_login(user)

        data = self.client.get("/api/me/overview/").json()
        self.assertEqual([p["id"] for p in data["projects"]], [project.pk])
        self.assertEqual(data["planned_work"][0]["hours"], "8.0")
        self.assertEqual([o["id"] for o in data["offers"]], [offer.pk])
        self.assertEqual(data["invoices"], [])
        self.assertEqual([d["id"] for d in data["deals"]], [deal.pk])

        with override_settings(FEATURES={FEATURES.CONTROLLING: F.ALWAYS}):
            data = self.client.get("/api/me/overview/").json()
            self.assertEqual(len(data["offers"]), 1)
            self.assertIsNone(data["deals"])
