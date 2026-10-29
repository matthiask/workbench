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
