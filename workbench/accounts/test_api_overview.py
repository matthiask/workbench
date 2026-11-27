from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.models import SpecialistField, Team
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
            _full_name="Hans Muster",
            _short_name="hm",
            email="hans@example.com",
            specialist_field=SpecialistField.objects.create(
                name="Development",
                value_type=factories.ValueTypeFactory.create(title="Programming"),
            ),
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
                    "specialist_field": "Development",
                    "value_type": "Programming",
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


class TeamsAPITest(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(_short_name="hm")
        self.client.force_login(self.user)

    def tearDown(self):
        deactivate_all()

    def post(self, url, data):
        return self.client.post(url, data, content_type="application/json")

    def patch(self, url, data):
        return self.client.patch(url, data, content_type="application/json")

    def locs(self, response):
        self.assertEqual(response.status_code, 422, response.content)
        return [error["loc"] for error in response.json()["detail"]]

    def test_create(self):
        """Teams are created through the web interface's form"""
        other = factories.UserFactory.create(_short_name="xy")
        response = self.post(
            "/api/teams/?dry_run=true", {"name": "Design", "members": ["HM", "xy"]}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["members"], ["hm", "xy"])
        self.assertEqual(Team.objects.count(), 0)

        data = self.post("/api/teams/", {"name": "Design", "members": ["hm", "xy"]})
        data = data.json()
        team = Team.objects.get()
        self.assertEqual(data["id"], team.pk)
        self.assertEqual(data["name"], "Design")
        self.assertEqual(set(team.members.all()), {self.user, other})

        # The form's rules: unique names, at least one member
        response = self.post("/api/teams/", {"name": "design", "members": []})
        self.assertEqual(
            self.locs(response),
            [["body", "data", "name"], ["body", "data", "members"]],
        )

        # Only active users
        other.is_active = False
        other.save()
        response = self.post(
            "/api/teams/", {"name": "Backend", "members": ["xy", "nobody"]}
        )
        self.assertEqual(
            self.locs(response),
            [["body", "data", "members", 0], ["body", "data", "members", 1]],
        )

    def test_update(self):
        """Renaming teams and changing their members, by ID or name"""
        team = factories.TeamFactory.create(name="Design")
        old = factories.UserFactory.create(_short_name="old", is_active=False)
        other = factories.UserFactory.create(_short_name="xy")
        team.members.add(self.user, old)

        response = self.patch(
            "/api/teams/design/", {"add_members": ["xy"], "remove_members": ["HM"]}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["members"], ["xy"])
        # Inactive members are dropped like in the web interface, which
        # doesn't show them
        self.assertEqual(set(team.members.all()), {other})

        data = self.patch(
            f"/api/teams/{team.pk}/?dry_run=true",
            {"name": "Frontend", "members": ["hm", "xy"]},
        ).json()
        self.assertEqual((data["name"], data["members"]), ("Frontend", ["hm", "xy"]))
        team.refresh_from_db()
        self.assertEqual(team.name, "Design")
        self.assertEqual(set(team.members.all()), {other})

        data = self.patch(f"/api/teams/{team.pk}/", {"name": "Frontend"}).json()
        self.assertEqual((data["name"], data["members"]), ("Frontend", ["xy"]))

        factories.TeamFactory.create(name="Backend")
        response = self.patch(
            f"/api/teams/{team.pk}/", {"name": "backend", "remove_members": ["xy"]}
        )
        self.assertEqual(
            self.locs(response),
            [["body", "data", "name"], ["body", "data", "members"]],
        )
        response = self.patch(f"/api/teams/{team.pk}/", {"add_members": ["old"]})
        self.assertEqual(self.locs(response), [["body", "data", "add_members", 0]])
        self.assertEqual(self.patch("/api/teams/nothing/", {}).status_code, 404)

    def test_delete(self):
        team = factories.TeamFactory.create(name="Design")
        team.members.add(self.user)

        data = self.client.delete("/api/teams/design/?dry_run=true").json()
        self.assertEqual((data["name"], data["members"]), ("Design", ["hm"]))
        self.assertTrue(Team.objects.exists())

        data = self.client.delete(f"/api/teams/{team.pk}/").json()
        self.assertEqual(data["id"], team.pk)
        self.assertFalse(Team.objects.exists())
        self.assertEqual(self.client.delete("/api/teams/1234/").status_code, 404)
