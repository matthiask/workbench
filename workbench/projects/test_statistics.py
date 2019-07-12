from datetime import date
from decimal import Decimal

from django.test import TestCase

from workbench import factories
from workbench.projects.models import Project
from workbench.projects.reporting import hours_per_customer, overdrawn_projects
from workbench.reporting import key_data
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

        response = self.client.get("/report/hours-per-customer/")
        self.assertContains(response, "Stunden pro Kundschaft")

        response = self.client.get("/report/hours-per-customer/?date_from=bla")
        self.assertRedirects(response, "/report/hours-per-customer/")

    def test_not_archived_hours_grouped_services_green_hours(self):
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

        hours = factories.LoggedHoursFactory.create(service=service1, hours=10)
        project = Project.objects.get()
        self.assertEqual(
            project.not_archived_total,
            {"total": Decimal("1800.00"), "hours_rate_undefined": Z},
        )

        self.assertEqual(project.project_invoices_subtotal, Decimal("1800.00"))

        grouped = project.grouped_services
        self.assertEqual(len(grouped["offers"]), 1)
        self.assertIs(grouped["offers"][0][0], None)  # Offer is None
        self.assertEqual(grouped["logged_hours"], Decimal(40))
        self.assertEqual(grouped["service_hours"], 0)
        self.assertEqual(grouped["total_logged_cost"], Decimal(3600))
        self.assertEqual(grouped["total_service_cost"], 0)
        self.assertEqual(grouped["total_logged_hours_rate_undefined"], Decimal(20))
        self.assertEqual(grouped["total_service_hours_rate_undefined"], 0)

        today = date.today()
        date_range = [date(today.year, 1, 1), date(today.year, 12, 31)]

        green_hours = key_data.green_hours(date_range)
        gh = green_hours[today.year]["year"]
        self.assertEqual(gh.profitable, 0)
        self.assertEqual(gh.overdrawn, Decimal(40))
        self.assertEqual(gh.maintenance, 0)
        self.assertEqual(gh.internal, 0)
        self.assertEqual(gh.total, Decimal(40))
        self.assertEqual(gh.green, 0)

        hpc = hours_per_customer(date_range)
        self.assertEqual(hpc["organizations"][0]["total_hours"], Decimal(40))
        self.assertEqual(len(hpc["organizations"]), 1)
        self.assertEqual(len(hpc["users"]), 3)

        hpc = hours_per_customer(date_range, users=[hours.rendered_by])
        self.assertEqual(hpc["organizations"][0]["total_hours"], Decimal(10))
        self.assertEqual(len(hpc["organizations"]), 1)
        self.assertEqual(len(hpc["users"]), 1)
