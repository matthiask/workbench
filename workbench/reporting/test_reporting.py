import datetime as dt
from decimal import Decimal

from django.core import mail
from django.test import TestCase

from freezegun import freeze_time

from workbench import factories
from workbench.reporting.accounting import send_accounting_files
from workbench.reporting.labor_costs import labor_costs
from workbench.reporting.models import MonthlyAccrual


class ReportingTest(TestCase):
    def test_send_accounting_files(self):
        factories.UserFactory.create(is_admin=True)
        factories.ProjectFactory.create()

        with freeze_time("2019-12-26"):
            send_accounting_files()
            self.assertEqual(len(mail.outbox), 0)

        with freeze_time("2020-01-01"):
            send_accounting_files()
            self.assertEqual(len(mail.outbox), 1)

    def test_accruals(self):
        obj = MonthlyAccrual.objects.for_cutoff_date(dt.date.today())
        self.assertEqual(obj.accruals, Decimal("0.00"))
        self.assertEqual(str(obj), obj.cutoff_date.strftime("%d.%m.%Y"))

    def test_labor_costs(self):
        user1 = factories.EmploymentFactory.create().user
        user2 = factories.EmploymentFactory.create(
            hourly_labor_costs=100, green_hours_target=75
        ).user

        service = factories.ServiceFactory.create()

        factories.LoggedHoursFactory.create(service=service, rendered_by=user1)
        factories.LoggedHoursFactory.create(service=service, rendered_by=user2)

        self.client.force_login(user1)
        response = self.client.get("/report/labor-costs/")
        self.assertEqual(response.status_code, 200)

        year = dt.date.today().year
        lc = labor_costs([dt.date(year, 1, 1), dt.date(year, 12, 31)])

        self.assertEqual(len(lc), 1)
        self.assertAlmostEqual(lc[0]["costs"], Decimal("100"))
        self.assertAlmostEqual(
            lc[0]["costs_with_green_hours_target"], Decimal("133.3333333")
        )
        self.assertEqual(lc[0]["hours"], 2)
        self.assertEqual(lc[0]["hours_with_rate_undefined"], 1)
