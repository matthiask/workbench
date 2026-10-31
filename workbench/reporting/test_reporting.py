import datetime as dt
from decimal import Decimal

from django.test import RequestFactory, TestCase

from workbench import factories
from workbench.invoices.models import Invoice
from workbench.projects.models import Project
from workbench.reporting import key_data
from workbench.reporting.labor_costs import labor_costs_by_cost_center
from workbench.reporting.models import Accruals
from workbench.reporting.third_party_costs import playing_bank
from workbench.reporting.views import DateRangeAndTeamFilterForm


class ReportingTest(TestCase):
    def test_accruals(self):
        """Accrual calculation does not crash..."""
        obj = Accruals.objects.for_cutoff_date(dt.date.today())
        self.assertEqual(obj.accruals, Decimal("0.00"))
        self.assertEqual(str(obj), obj.cutoff_date.strftime("%d.%m.%Y"))

    def test_accruals_leave_out_internal_projects(self):
        """Accruals are based on projects and leave out internal ones, like
        the cash data API"""
        for type in [Project.ORDER, Project.INTERNAL]:
            project = factories.ProjectFactory.create(type=type)
            factories.InvoiceFactory.create(
                project=project,
                customer=project.customer,
                contact=project.contact,
                type=Invoice.FIXED,
                subtotal=100,
                status=Invoice.SENT,
                due_on=dt.date.today(),
            )
        self.assertEqual(Accruals.objects.accruals(dt.date.today()), -100)

    def test_labor_costs(self):
        """The labor costs report does a few things"""
        user1 = factories.EmploymentFactory.create().user
        user2 = factories.EmploymentFactory.create(
            hourly_labor_costs=100, green_hours_target=75
        ).user

        service = factories.ServiceFactory.create()

        factories.LoggedHoursFactory.create(service=service, rendered_by=user1)
        factories.LoggedHoursFactory.create(service=service, rendered_by=user2)
        factories.LoggedCostFactory.create(
            service=service, third_party_costs=10, cost=15
        )

        self.client.force_login(user1)
        response = self.client.get("/report/labor-costs/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/report/labor-costs/?project={service.project_id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            f"/report/labor-costs/?cost_center={factories.CostCenterFactory.create().pk}"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/report/labor-costs/?users=all")
        self.assertEqual(response.status_code, 200)

        year = dt.date.today().year
        lc = labor_costs_by_cost_center([dt.date(year, 1, 1), dt.date(year, 12, 31)])
        lcp = lc["cost_centers"][0]["projects"]

        self.assertEqual(len(lcp), 1)
        self.assertAlmostEqual(lcp[0]["costs"], Decimal(100))
        self.assertAlmostEqual(
            lcp[0]["costs_with_green_hours_target"], Decimal("133.3333333")
        )
        self.assertEqual(lcp[0]["hours"], 2)
        self.assertEqual(lcp[0]["hours_with_rate_undefined"], 1)

        self.assertEqual(lcp[0]["third_party_costs"], Decimal(10))
        self.assertEqual(lcp[0]["revenue"], Decimal(115))

    def test_teams_filter(self):
        """Filtering by teams and individuals"""
        rf = RequestFactory()
        req = rf.get("/")

        user1 = factories.UserFactory.create()
        user2 = factories.UserFactory.create()
        team = factories.TeamFactory.create()
        team.members.add(user1)

        form = DateRangeAndTeamFilterForm({"team": team.id}, request=req)
        self.assertTrue(form.is_valid())
        self.assertEqual(set(form.users()), {user1})

        form = DateRangeAndTeamFilterForm({"team": -user2.id}, request=req)
        self.assertTrue(form.is_valid())
        self.assertEqual(set(form.users()), {user2})

    def test_projected_gross_margin_skips_empty_projections(self):
        """Projections of zero don't keep the open amount from older ones"""
        project = factories.ProjectFactory.create()
        for month, gross_margin in [(1, 500), (2, 0), (3, 300)]:
            factories.ProjectedInvoiceFactory.create(
                project=project,
                invoiced_on=dt.date(2026, month, 15),
                gross_margin=gross_margin,
            )

        (data,) = key_data.projected_gross_margin(
            Project.objects.filter(pk=project.pk)
        )["projects"]
        self.assertEqual(data["monthly"], {(2026, 1): 500, (2026, 3): 300})

    def test_third_party_costs_by_month_are_deducted_once(self):
        """A project's third party costs are deducted once: the larger of
        those on invoices and the logged ones, like in squeeze"""
        project = factories.ProjectFactory.create()
        service = factories.ServiceFactory.create(project=project)
        factories.LoggedCostFactory.create(
            service=service,
            cost=600,
            third_party_costs=600,
            rendered_on=dt.date(2026, 3, 10),
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.FIXED,
            subtotal=1000,
            third_party_costs=600,
            status=Invoice.SENT,
            invoiced_on=dt.date(2026, 4, 1),
            due_on=dt.date(2026, 4, 30),
        )
        factories.LoggedCostFactory.create(
            service=service,
            cost=100,
            third_party_costs=100,
            rendered_on=dt.date(2026, 5, 10),
        )

        # Down payments may be the only invoices with third party costs
        recurring = factories.ProjectFactory.create()
        factories.InvoiceFactory.create(
            project=recurring,
            customer=recurring.customer,
            contact=recurring.contact,
            type=Invoice.DOWN_PAYMENT,
            subtotal=1000,
            third_party_costs=300,
            status=Invoice.SENT,
            invoiced_on=dt.date(2026, 6, 1),
            due_on=dt.date(2026, 6, 30),
        )

        costs = key_data.third_party_costs_by_month([
            dt.date(2026, 1, 1),
            dt.date(2026, 12, 31),
        ])
        self.assertEqual(
            {month: total for month, total in costs.items() if total},
            {(2026, 3): -600, (2026, 5): -100, (2026, 6): -300},
        )

    def test_playing_bank(self):
        """Third party costs passed on to customers count down payments and
        the final invoice once, offered ones only on budgeted services"""
        project = factories.ProjectFactory.create()
        for type in [Invoice.DOWN_PAYMENT, Invoice.FIXED]:
            factories.InvoiceFactory.create(
                project=project,
                customer=project.customer,
                contact=project.contact,
                type=type,
                subtotal=1000,
                third_party_costs=600,
                status=Invoice.SENT,
                due_on=dt.date.today(),
            )
        factories.ServiceFactory.create(project=project, third_party_costs=500)
        factories.ServiceFactory.create(
            project=project, third_party_costs=200, is_optional=True
        )

        (row,) = playing_bank(Project.objects.all())["projects"]
        self.assertEqual(row["invoiced"], 600)
        self.assertEqual(row["offered"], 500)
