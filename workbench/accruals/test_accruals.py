import datetime as dt
from decimal import Decimal

from django.test import TestCase

from freezegun import freeze_time

from workbench import factories
from workbench.accruals.models import Accrual, CutoffDate
from workbench.accruals.tasks import create_accruals_for_last_month
from workbench.reporting import key_data
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import messages


class AccrualsTest(TestCase):
    def test_cutoff_days(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.post("/accruals/create/", {"day": ""})
        self.assertContains(response, "This field is required.")
        response = self.client.post("/accruals/create/", {"day": "2019-01-31"})
        day = CutoffDate.objects.get()
        self.assertRedirects(response, day.urls["detail"])
        response = self.client.post(day.urls["delete"])
        self.assertRedirects(response, day.urls["list"])
        self.assertEqual(
            messages(response),
            ["cutoff date '31.01.2019' has been deleted successfully."],
        )

    def test_cutoff_day_warning(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.post("/accruals/create/", {"day": "2019-01-01"})
        self.assertContains(response, "Unusual cutoff date (not last of the month).")

        response = self.client.post(
            "/accruals/create/",
            {"day": "2019-01-01", WarningsForm.ignore_warnings_id: "unusual-cutoff"},
        )
        self.assertEqual(response.status_code, 302)

    def test_cutoff_days_with_accruals(self):
        project = factories.ProjectFactory.create()

        factories.InvoiceFactory.create(
            project=project,
            type=factories.Invoice.FIXED,
            invoiced_on=dt.date(2018, 12, 1),
            status=factories.Invoice.SENT,
            subtotal=100,
        )
        down_payment = factories.InvoiceFactory.create(
            project=project,
            type=factories.Invoice.DOWN_PAYMENT,
            invoiced_on=dt.date(2018, 12, 2),
            status=factories.Invoice.SENT,
            subtotal=100,
        )

        service = factories.ServiceFactory.create(
            project=project, effort_type="Programmierung", effort_rate=150
        )
        factories.LoggedHoursFactory.create(
            service=service, hours=1, rendered_on=dt.date(2018, 12, 15)
        )
        factories.LoggedCostFactory.create(
            service=service, cost=0, rendered_on=dt.date(2018, 12, 15)
        )

        self.client.force_login(factories.UserFactory.create())
        response = self.client.post("/accruals/create/", {"day": "2018-12-31"})
        day = CutoffDate.objects.get()
        self.assertRedirects(response, day.urls["detail"])

        response = self.client.get(day.urls["update"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(messages(response), [])

        response = self.client.get(day.urls["detail"] + "?create_accruals=1")
        self.assertRedirects(response, day.urls["detail"])
        self.assertEqual(messages(response), ["Generated accruals."])

        self.assertEqual(Accrual.objects.count(), 1)

        response = self.client.post(day.urls["delete"])
        self.assertRedirects(response, day.urls["detail"])
        self.assertEqual(
            messages(response),
            ["Cannot modify a cutoff date where accrual records already exist."],
        )

        response = self.client.get(day.urls["update"])
        self.assertRedirects(response, day.urls["detail"])
        self.assertEqual(
            messages(response),
            ["Cannot modify a cutoff date where accrual records already exist."],
        )

        response = self.client.get(day.urls["detail"] + "?xlsx=1")
        self.assertEqual(response.status_code, 200)

        accrual = Accrual.objects.get()
        self.assertEqual(accrual.cutoff_date, dt.date(2018, 12, 31))
        self.assertEqual(accrual.work_progress, 50)  # 100 of fixed, 50 of down payment
        response = self.client.post(
            day.urls["detail"], {"id": accrual.id, "work_progress": 60}
        )
        self.assertEqual(response.status_code, 202)
        accrual.refresh_from_db()
        self.assertEqual(accrual.work_progress, 60)

        Accrual.objects.create(
            invoice=down_payment,
            cutoff_date=dt.date(2019, 1, 31),
            work_progress=80,
            logbook=0,
        )

        Accrual.objects.create(
            invoice=down_payment,
            cutoff_date=dt.date(2019, 3, 31),
            work_progress=100,
            logbook=0,
        )

        # print(key_data.accruals_by_month())
        accruals = key_data.accruals_by_month(
            [dt.date(2010, 1, 1), dt.date(2019, 11, 1)]
        )
        self.assertEqual(len(accruals), 3)

        self.assertEqual(accruals[(2018, 12)]["accrual"], Decimal(-40))
        self.assertEqual(accruals[(2018, 12)]["delta"], Decimal(-40))

        self.assertEqual(accruals[(2019, 1)]["accrual"], Decimal(-20))
        self.assertEqual(accruals[(2019, 1)]["delta"], Decimal(20))

        self.assertEqual(accruals[(2019, 3)]["accrual"], Decimal(0))
        self.assertEqual(accruals[(2019, 3)]["delta"], Decimal(20))

        invoiced = key_data.gross_profit_by_month(
            [dt.date(2018, 1, 1), dt.date(2019, 2, 28)]
        )
        self.assertEqual(len(invoiced), 1)
        self.assertEqual(invoiced[(2018, 12)]["total_excl_tax"], Decimal(200))

        invoiced = key_data.gross_margin_by_month(
            [dt.date(2018, 1, 1), dt.date(2019, 2, 28)]
        )
        self.assertEqual(len(invoiced), 2)
        self.assertEqual(invoiced[0]["gross_margin"], Decimal(160))

        factories.LoggedCostFactory.create(
            rendered_on=dt.date(2018, 12, 25), third_party_costs=10
        )

        invoiced = key_data.gross_margin_by_month(
            [dt.date(2018, 1, 1), dt.date(2019, 3, 31)]
        )
        self.assertEqual(len(invoiced), 3)
        self.assertEqual(invoiced[0]["month"], (2018, 12))
        self.assertEqual(
            invoiced[0]["gross_margin"], Decimal(150)
        )  # 160 - 10 logged cost
        self.assertEqual(invoiced[1]["month"], (2019, 1))
        self.assertEqual(invoiced[1]["gross_margin"], Decimal(20))
        self.assertEqual(invoiced[2]["month"], (2019, 3))
        self.assertEqual(invoiced[2]["gross_margin"], Decimal(20))

    def test_future_cutoff_dates(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.post("/accruals/create/", {"day": "2099-01-31"})
        day = CutoffDate.objects.get()
        self.assertRedirects(response, day.urls["detail"])

        response = self.client.get(day.urls["detail"] + "?create_accruals=1")
        self.assertRedirects(response, day.urls["detail"])
        self.assertEqual(
            messages(response), ["Cannot generate accruals for future cutoff dates."]
        )

    def test_list(self):
        self.client.force_login(factories.UserFactory.create())
        self.assertEqual(self.client.get("/accruals/").status_code, 200)
        self.assertEqual(self.client.get("/accruals/?q=foo").status_code, 200)

    @freeze_time("2019-10-01")
    def test_task_on_first(self):
        create_accruals_for_last_month()
        self.assertEqual(CutoffDate.objects.get().day, dt.date(2019, 9, 30))

    @freeze_time("2019-10-02")
    def test_task_on_other(self):
        create_accruals_for_last_month()
        self.assertEqual(CutoffDate.objects.count(), 0)

    def test_accruals_list(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        accrual = CutoffDate.objects.create(day=dt.date.today())

        def valid(p):
            response = self.client.get(accrual.urls["detail"] + p)
            self.assertEqual(response.status_code, 200)

        valid("")
        valid("?owned_by=0")
        valid("?owned_by=%s" % user.pk)

        response = self.client.get(accrual.urls["detail"] + "?owned_by=abc")
        self.assertRedirects(response, accrual.urls["detail"])
        self.assertEqual(messages(response), [])
