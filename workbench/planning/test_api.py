import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.offers.models import Offer
from workbench.tools.validation import in_days, monday


class PlanningAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_context(self):
        """The context contains what's needed to plan and the import schema"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        factories.OfferFactory.create(project=project, status=Offer.DECLINED)
        factories.ServiceFactory.create(
            project=project, offer=offer, title="Design", service_hours=20
        )
        milestone = factories.MilestoneFactory.create(project=project, date=in_days(30))
        factories.PlannedWorkFactory.create(
            project=project, milestone=milestone, weeks=[monday()]
        )
        factories.AbsenceFactory.create(user=project.owned_by)
        factories.AbsenceFactory.create(starts_on=in_days(-30), ends_on=in_days(-20))
        inactive = factories.UserFactory.create(is_active=False)
        service_type = factories.service_types().consulting

        url = f"/api/projects/{project.pk}/planning/context/"
        self.assertEqual(self.client.get(url).status_code, 401)

        self.client.force_login(project.owned_by)
        data = self.client.get(url).json()

        self.assertEqual(data["project"]["code"], project.code)
        self.assertEqual([o["code"] for o in data["offers"]], [offer.code])
        self.assertEqual(data["offers"][0]["services"][0]["title"], "Design")
        self.assertEqual(data["milestones"][0]["id"], milestone.pk)
        self.assertEqual(data["planned_work"][0]["milestone"], milestone.pk)
        self.assertEqual(data["planned_work"][0]["weeks"], [monday().isoformat()])
        self.assertEqual(
            [a["user"] for a in data["absences"]], [project.owned_by.email]
        )

        emails = [user["email"] for user in data["users"]]
        self.assertIn(project.owned_by.email, emails)
        self.assertNotIn(inactive.email, emails)

        work = data["import_schema"]["$defs"]["PlannedWorkIn"]["properties"]
        self.assertEqual(sorted(work["user"]["enum"]), sorted(emails))
        self.assertIn(service_type.title, work["service_type"]["enum"])
        self.assertEqual(work["offer"]["anyOf"][0]["enum"], [offer.code])

        self.assertEqual(
            self.client.get("/api/projects/0/planning/context/").status_code, 404
        )

    def test_import(self):
        """Importing adds milestones and planned work, or nothing at all"""
        project = factories.ProjectFactory.create()
        user = project.owned_by
        offer = factories.OfferFactory.create(project=project)
        declined = factories.OfferFactory.create(project=project, status=Offer.DECLINED)
        existing = factories.MilestoneFactory.create(project=project, date=in_days(90))
        factories.service_types()
        self.client.force_login(user)

        url = f"/api/projects/{project.pk}/planning/import/"
        start = monday() + dt.timedelta(days=14)
        data = {
            "milestones": [
                {"key": "golive", "title": "Go-Live", "date": in_days(60).isoformat()}
            ],
            "planned_work": [
                {
                    "title": "Concept",
                    "user": user.email,
                    "service_type": "consulting",
                    "offer": offer.code,
                    "milestone": "golive",
                    # Not a monday, and listed twice
                    "weeks": [
                        (start + dt.timedelta(days=2)).isoformat(),
                        start.isoformat(),
                    ],
                    "planned_hours": 12.25,
                },
                {
                    "title": "Production",
                    "user": user.email,
                    "service_type": "production",
                    "milestone": existing.pk,
                    "weeks": [start.isoformat()],
                    "planned_hours": 20,
                    "is_provisional": False,
                },
            ],
        }

        response = self.client.post(
            url + "?dry_run=true", data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["milestones"][0]["id"], None)
        self.assertEqual(result["planned_work"][0]["milestone"], "Go-Live")
        self.assertEqual(result["planned_work"][0]["weeks"], [start.isoformat()])
        self.assertEqual(result["planned_work"][0]["planned_hours"], "12.2")
        self.assertEqual(result["warnings"], [])
        self.assertEqual(project.planned_work.count(), 0)
        self.assertEqual(project.milestones.count(), 1)

        response = self.client.post(url, data, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        concept, production = project.planned_work.order_by("pk")
        self.assertEqual(concept.milestone.title, "Go-Live")
        self.assertEqual(concept.offer, offer)
        self.assertEqual(concept.created_by, user)
        self.assertTrue(concept.is_provisional)
        self.assertEqual(production.milestone, existing)
        self.assertFalse(production.is_provisional)

        # Invalid references are reported per entry, and nothing is saved
        data["milestones"].append(data["milestones"][0])
        data["planned_work"][0] |= {
            "user": "nobody@example.com",
            "service_type": "unknown",
            "offer": declined.code,
            "milestone": "missing",
        }
        data["planned_work"][1]["weeks"] = [in_days(100).isoformat()]
        response = self.client.post(url, data, content_type="application/json")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"][2:] for error in response.json()["detail"]],
            [
                ["milestones", 1, "key"],
                ["planned_work", 0, "user"],
                ["planned_work", 0, "service_type"],
                ["planned_work", 0, "offer"],
                ["planned_work", 0, "milestone"],
            ],
        )
        self.assertEqual(project.planned_work.count(), 2)
        self.assertEqual(project.milestones.count(), 2)

        # Work after the milestone is only a warning
        response = self.client.post(
            url + "?dry_run=true",
            {"planned_work": [data["planned_work"][1]]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [warning["loc"][2:] for warning in response.json()["warnings"]],
            [["planned_work", 0, "weeks"]],
        )

        # The schema is enforced too
        response = self.client.post(
            url,
            {"planned_work": [{"title": "Nothing else"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
