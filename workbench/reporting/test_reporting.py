import datetime as dt
from decimal import Decimal

from django.core import mail
from django.test import RequestFactory, TestCase

from time_machine import travel

from workbench import factories
from workbench.reporting.accounting import send_accounting_files
from workbench.reporting.labor_costs import labor_costs_by_cost_center
from workbench.reporting.models import Accruals
from workbench.reporting.views import DateRangeAndTeamFilterForm


class ReportingTest(TestCase):
    def test_send_accounting_files(self):
        """Accounting files are automatically sent on the first day of the year"""
        factories.UserFactory.create(is_admin=True)
        factories.ProjectFactory.create()

        with travel("2019-12-26 12:00"):
            send_accounting_files()
            self.assertEqual(len(mail.outbox), 0)

        with travel("2020-01-01 12:00"):
            send_accounting_files()
            self.assertEqual(len(mail.outbox), 1)

    def test_accruals(self):
        """Accrual calculation does not crash..."""
        obj = Accruals.objects.for_cutoff_date(dt.date.today())
        self.assertEqual(obj.accruals, Decimal("0.00"))
        self.assertEqual(str(obj), obj.cutoff_date.strftime("%d.%m.%Y"))

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

        response = self.client.get(
            "/report/labor-costs/?project={}".format(service.project_id)
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            "/report/labor-costs/?cost_center={}".format(
                factories.CostCenterFactory.create().pk
            )
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/report/labor-costs/?users=all")
        self.assertEqual(response.status_code, 200)

        year = dt.date.today().year
        lc = labor_costs_by_cost_center([dt.date(year, 1, 1), dt.date(year, 12, 31)])
        lcp = lc["cost_centers"][0]["projects"]

        self.assertEqual(len(lcp), 1)
        self.assertAlmostEqual(lcp[0]["costs"], Decimal("100"))
        self.assertAlmostEqual(
            lcp[0]["costs_with_green_hours_target"], Decimal("133.3333333")
        )
        self.assertEqual(lcp[0]["hours"], 2)
        self.assertEqual(lcp[0]["hours_with_rate_undefined"], 1)

        self.assertEqual(lcp[0]["third_party_costs"], Decimal("10"))
        self.assertEqual(lcp[0]["revenue"], Decimal("115"))

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
