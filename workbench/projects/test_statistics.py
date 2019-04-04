from decimal import Decimal

from django.test import TestCase

from workbench import factories
from workbench.projects.reporting import overdrawn_projects


class StatisticsTest(TestCase):
    def test_stats(self):
        service1 = factories.ServiceFactory.create(effort_hours=2)
        factories.ServiceFactory.create(effort_hours=4)

        user = factories.UserFactory.create()

        op = list(overdrawn_projects())
        self.assertEqual(op, [])

        factories.LoggedHoursFactory.create(
            service=service1, created_by=user, rendered_by=user, hours=10
        )

        op = list(overdrawn_projects())
        self.assertEqual(len(op), 1)
        self.assertEqual(
            op,
            [
                {
                    "project": service1.project,
                    "logged_hours": Decimal("10.0"),
                    "service_hours": Decimal("2.0"),
                    "delta": Decimal("8.0"),
                }
            ],
        )

    def test_view(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/report/overdrawn-projects/")
        self.assertContains(response, "Überzogene Projekte")
