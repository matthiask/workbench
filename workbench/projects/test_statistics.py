from decimal import Decimal

from django.test import TestCase

from workbench import factories
from workbench.projects.models import Project
from workbench.projects.reporting import overdrawn_projects
from workbench.tools.models import Z


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

    def test_not_archived_hours(self):
        service1 = factories.ServiceFactory.create(effort_rate=180, effort_type="Any")
        service2 = factories.ServiceFactory.create(project=service1.project)

        project = Project.objects.get()
        self.assertEqual(
            project.not_archived_total, {"total": Z, "hours_rate_undefined": Z}
        )

        factories.LoggedHoursFactory.create(service=service1, hours=10)
        factories.LoggedHoursFactory.create(service=service2, hours=20)

        project = Project.objects.get()
        self.assertEqual(
            project.not_archived_total,
            {"total": Decimal("1800.00"), "hours_rate_undefined": Decimal("20.00")},
        )

        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=factories.Invoice.SERVICES,
        )
        invoice.create_services_from_logbook(project.services.all())

        project = Project.objects.get()
        self.assertEqual(
            project.not_archived_total, {"total": Z, "hours_rate_undefined": Z}
        )

        factories.LoggedHoursFactory.create(service=service1, hours=10)
        project = Project.objects.get()
        self.assertEqual(
            project.not_archived_total,
            {"total": Decimal("1800.00"), "hours_rate_undefined": Z},
        )
