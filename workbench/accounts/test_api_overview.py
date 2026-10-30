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

    def test_users(self):
        """Users can be searched, active users by default"""
        user = factories.UserFactory.create(
            _full_name="Hans Muster", _short_name="hm", email="hans@example.com"
        )
        factories.TeamFactory.create(name="Design").members.add(user)
        factories.UserFactory.create(_full_name="Hans Alt", is_active=False)
        self.client.force_login(user)

        data = self.client.get("/api/users/?q=hans").json()["items"]
        self.assertEqual(
            data,
            [
                {
                    "id": user.pk,
                    "url": f"http://testserver{user.get_absolute_url()}",
                    "short_name": "hm",
                    "full_name": "Hans Muster",
                    "email": "hans@example.com",
                    "is_active": True,
                    "teams": ["Design"],
                }
            ],
        )
        data = self.client.get("/api/users/?q=hans&include_inactive=true").json()[
            "items"
        ]
        self.assertEqual(len(data), 2)
        data = self.client.get("/api/users/?q=HM+example").json()["items"]
        self.assertEqual([u["id"] for u in data], [user.pk])

    def test_teams(self):
        """Teams with their active members"""
        user = factories.UserFactory.create(_short_name="hm")
        team = factories.TeamFactory.create(name="Design")
        team.members.add(
            user, factories.UserFactory.create(_short_name="old", is_active=False)
        )
        factories.TeamFactory.create(name="Backend")
        self.client.force_login(user)

        data = self.client.get("/api/teams/?q=des").json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["name"], "Design")
        self.assertEqual(data["items"][0]["members"], ["hm"])
        self.assertEqual(self.client.get("/api/teams/").json()["count"], 2)
