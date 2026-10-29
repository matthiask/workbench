import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.validation import monday


class ProjectsAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_project_list(self):
        """Projects can be searched"""
        project = factories.ProjectFactory.create(title="Relaunch")
        factories.ProjectFactory.create(title="Other")
        self.client.force_login(project.owned_by)

        data = self.client.get("/api/projects/?q=relaunch").json()
        self.assertEqual([p["id"] for p in data], [project.pk])

    def test_stats(self):
        """Statistics of the selected projects"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(
            project=project,
            status=Offer.ACCEPTED,
            offered_on=dt.date.today(),
            valid_until=dt.date.today(),
        )
        service = factories.ServiceFactory.create(
            project=project,
            offer=offer,
            title="Design",
            effort_type="Design",
            effort_hours=10,
            effort_rate=200,
        )
        user = factories.UserFactory.create(_short_name="ab")
        factories.LoggedHoursFactory.create(service=service, rendered_by=user, hours=3)
        factories.LoggedHoursFactory.create(service=service, rendered_by=user, hours=2)
        factories.PlannedWorkFactory.create(
            project=project, user=user, weeks=[monday()], planned_hours=8
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            status=Invoice.SENT,
            subtotal=600,
        )
        factories.InvoiceFactory.create(project=project, customer=project.customer)
        closed = factories.ProjectFactory.create(closed_on=dt.date(2026, 6, 1))
        factories.ProjectFactory.create(closed_on=dt.date(2025, 6, 1))
        self.client.force_login(project.owned_by)

        self.assertEqual(self.client.get("/api/projects/stats/").status_code, 400)

        data = self.client.get(f"/api/projects/stats/?ids={project.pk}").json()
        self.assertEqual(len(data), 1)
        stats = data[0]
        self.assertEqual(stats["project"]["id"], project.pk)
        self.assertEqual(
            stats["hours"],
            {
                "offered": "10.0",
                "logged": "5.0",
                "logged_rate_undefined": "0.0",
                "planned": "8.0",
            },
        )
        self.assertEqual(stats["amounts"]["sold"], "2000.00")
        self.assertEqual(stats["amounts"]["invoiced"], "600.00")
        self.assertEqual(stats["amounts"]["effort_cost"], "1000.00")
        self.assertEqual(stats["amounts"]["not_invoiced"], "400.00")
        self.assertEqual(stats["gross_margin"]["gross_margin"], "2000.00")
        self.assertEqual(stats["services"][0]["effort_rate"], "200.00")
        self.assertEqual(
            stats["logged_hours"],
            [{"service": service.pk, "user": "ab", "hours": "5.0"}],
        )
        self.assertEqual(
            stats["planned_hours"],
            [{"user": "ab", "planned_hours": "8.0", "is_provisional": False}],
        )
        self.assertEqual([i["total_excl_tax"] for i in stats["invoices"]], ["600.00"])

        data = self.client.get(
            "/api/projects/stats/?open=true&closed_since=2026-01-01"
        ).json()
        self.assertEqual([s["project"]["id"] for s in data], [project.pk, closed.pk])

        data = self.client.get(
            f"/api/projects/stats/?ids={project.pk}&ids={closed.pk}"
        ).json()
        self.assertEqual(len(data), 2)
        self.assertEqual(Decimal(data[1]["hours"]["logged"]), 0)

    def test_create(self):
        """Projects are validated like in the web interface"""
        user = factories.UserFactory.create()
        other = factories.UserFactory.create(_short_name="ot")
        customer = factories.OrganizationFactory.create()
        contact = factories.PersonFactory.create(organization=customer)
        self.client.force_login(user)

        data = {
            "title": "Relaunch",
            "customer": customer.pk,
            "contact": contact.pk,
        }
        response = self.client.post(
            "/api/projects/?dry_run=true", data, content_type="application/json"
        )
        self.assertEqual(response.json()["id"], None)
        self.assertFalse(Project.objects.exists())

        response = self.client.post(
            "/api/projects/", data, content_type="application/json"
        )
        project = Project.objects.get()
        self.assertEqual(response.json()["id"], project.pk)
        self.assertEqual(project.owned_by, user)
        self.assertEqual(project.contact, contact)
        self.assertEqual(project.type, Project.ORDER)

        response = self.client.post(
            "/api/projects/",
            data | {"owned_by": "ot", "type": "maintenance"},
            content_type="application/json",
        )
        project = Project.objects.get(pk=response.json()["id"])
        self.assertEqual(project.owned_by, other)
        self.assertEqual(project.type, Project.MAINTENANCE)

        # Warnings of the web interface are errors
        response = self.client.post(
            "/api/projects/",
            data | {"contact": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [{"loc": ["body", "data"], "msg": "No contact selected."}],
        )

        response = self.client.post(
            "/api/projects/",
            data | {"customer": 0, "owned_by": "nobody"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [["body", "data", "owned_by"]],
        )

        response = self.client.post(
            "/api/projects/",
            data | {"customer": 0},
            content_type="application/json",
        )
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [["body", "data", "customer"]],
        )
