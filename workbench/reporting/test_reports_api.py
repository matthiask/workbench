import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from time_machine import travel

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.invoices.models import Invoice
from workbench.tools.validation import in_days, monday


class ReportsAPITest(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create(_short_name="ab")
        self.client.force_login(self.user)

    def get(self, url, **params):
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_periods(self):
        """Periods are years, months or quarters, the dates override them"""
        url = "/api/hours-per-customer/"
        data = self.get(url, period="2026-Q3")
        self.assertEqual(
            (data["date_from"], data["date_until"]), ("2026-07-01", "2026-09-30")
        )
        data = self.get(url, period="2026-2")
        self.assertEqual(
            (data["date_from"], data["date_until"]), ("2026-02-01", "2026-02-28")
        )
        data = self.get(url, period="2026", date_until="2026-03-31")
        self.assertEqual(
            (data["date_from"], data["date_until"]), ("2026-01-01", "2026-03-31")
        )
        data = self.get(url)
        self.assertEqual(data["date_from"], monday().isoformat())

        for period in ["2026-13", "2026-Q5", "last month", "2026-00"]:
            response = self.client.get(url, {"period": period})
            self.assertEqual(response.status_code, 422)
        response = self.client.get(
            url, {"period": "2026-09", "date_from": "2026-10-01"}
        )
        self.assertEqual(response.status_code, 422)

    @travel("2026-02-11 12:00")
    def test_relative_periods(self):
        """Periods relative to today"""
        for period, expected in [
            ("last-week", ("2026-02-02", "2026-02-08")),
            ("this-week", ("2026-02-09", "2026-02-15")),
            ("next-week", ("2026-02-16", "2026-02-22")),
            ("last-month", ("2026-01-01", "2026-01-31")),
            ("next-month", ("2026-03-01", "2026-03-31")),
            ("last-quarter", ("2025-10-01", "2025-12-31")),
            ("this-quarter", ("2026-01-01", "2026-03-31")),
            ("next-quarter", ("2026-04-01", "2026-06-30")),
            ("last-year", ("2025-01-01", "2025-12-31")),
        ]:
            with self.subTest(period=period):
                data = self.get("/api/hours-per-customer/", period=period)
                self.assertEqual((data["date_from"], data["date_until"]), expected)

        data = self.get(
            "/api/hours-per-customer/", period="last-month", date_from="2026-01-15"
        )
        self.assertEqual(data["date_from"], "2026-01-15")
        response = self.client.get("/api/hours-per-customer/", {"period": "last-day"})
        self.assertEqual(response.status_code, 422)

    def test_users(self):
        """Users are filtered by short name or team"""
        other = factories.UserFactory.create(_short_name="cd")
        service = factories.ServiceFactory.create()
        for user in [self.user, other]:
            factories.LoggedHoursFactory.create(
                service=service, rendered_by=user, hours=2
            )

        url = "/api/hours-per-customer/"
        self.assertEqual(self.get(url)["total_hours"], 4)
        data = self.get(url, user="AB")
        self.assertEqual(data["total_hours"], 2)
        self.assertEqual(data["users"], {"ab": 2})
        self.assertEqual(self.get(url, user=["ab", "cd"])["total_hours"], 4)

        team = factories.TeamFactory.create(name="Design")
        team.members.add(other)
        self.assertEqual(self.get(url, team="design")["users"], {"cd": 2})

        response = self.client.get(url, {"user": ["ab", "xy"]})
        self.assertEqual(response.status_code, 422)
        self.assertIn("xy", response.content.decode())
        self.assertEqual(self.client.get(url, {"team": "nope"}).status_code, 422)

    def test_hours(self):
        """Hours per customer and type, green hours, planning and logging"""
        service = factories.ServiceFactory.create()
        factories.LoggedHoursFactory.create(
            service=service, rendered_by=self.user, hours=3
        )
        factories.PlannedWorkFactory.create(
            project=service.project,
            user=self.user,
            planned_hours=10,
            weeks=[monday()],
        )

        data = self.get("/api/hours-per-customer/")
        [customer] = data["customers"]
        self.assertEqual(customer["customer"]["id"], service.project.customer_id)
        self.assertEqual(customer["users"], {"ab": 3})

        data = self.get("/api/hours-per-type/")
        [user] = data["users"]
        self.assertEqual(user["user"], "ab")
        self.assertEqual(user["external"], 3)
        self.assertEqual(user["types"][0]["reached_percentage"], 100)

        data = self.get("/api/green-hours/")
        self.assertEqual(data["users"][0]["user"], "ab")
        self.assertEqual(data["users"][0]["overdrawn"], 3)
        self.assertEqual(data["total"]["total"], 3)

        data = self.get("/api/planning-vs-logbook/", user="ab")
        self.assertEqual(data["planned"], 10)
        self.assertEqual(data["logged"], 3)
        [customer] = data["customers"]
        self.assertEqual(customer["weeks"][0]["week"], monday().isoformat())

        data = self.get("/api/logging/")
        [user] = data["users"]
        self.assertEqual(user["logged_hours"]["sum"], 3)
        self.assertIsInstance(user["logging"], str)

    def test_controlling(self):
        """Budget statistics, third party costs, open items and planned
        invoicing"""
        project = factories.ProjectFactory.create(owned_by=self.user)
        service = factories.ServiceFactory.create(project=project, effort_rate=100)
        factories.LoggedHoursFactory.create(service=service, hours=5)
        factories.LoggedCostFactory.create(
            service=service, cost=150, third_party_costs=120
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            status=Invoice.SENT,
            invoiced_on=in_days(-40),
            due_on=in_days(-10),
            subtotal=200,
        )
        factories.ProjectedInvoiceFactory.create(
            project=project, invoiced_on=in_days(30), gross_margin=1000
        )

        data = self.get("/api/project-budget-statistics/")
        [row] = data["projects"]
        self.assertEqual(row["project"]["id"], project.id)
        self.assertEqual(row["owned_by"], "ab")
        self.assertEqual(row["effort_cost"], 500)
        self.assertEqual(row["delta"], 450)
        self.assertEqual(data["overall"]["delta_positive"], 450)
        self.assertEqual(
            self.get("/api/project-budget-statistics/", owned_by="AB")["projects"],
            data["projects"],
        )
        self.assertEqual(
            self.get("/api/project-budget-statistics/", internal=True)["projects"], []
        )
        response = self.client.get(
            "/api/project-budget-statistics/", {"owned_by": "xy"}
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("owned_by", response.content.decode())

        data = self.get("/api/third-party-costs/")
        [row] = data["projects"]
        self.assertEqual(row["logged"], {"past": 120, "future": 0})
        self.assertEqual(data["total_not_invoiced"], 120)

        data = self.get("/api/open-items/")
        self.assertEqual(data["total_excl_tax"], 200)
        self.assertEqual(data["invoices"][0]["project"]["id"], project.id)
        data = self.get("/api/open-items/", cutoff_date=in_days(-50).isoformat())
        self.assertEqual(data["invoices"], [])

        data = self.get("/api/projected-gross-margin/")
        month = f"{in_days(30):%Y-%m}"
        # The invoice's gross margin (200 - 120) uses up the projection
        self.assertEqual(data["monthly"], {month: 920})
        self.assertEqual(data["projects"][0]["not_invoiced"], 920)

    def test_key_data_month(self):
        """Key data of a given month"""
        self.assertEqual(
            self.get("/api/key-data/", month="2026-01")["month"], "2026-01"
        )
        response = self.client.get("/api/key-data/", {"month": "January"})
        self.assertEqual(response.status_code, 422)

    def test_squeeze(self):
        """Squeeze splits the gross margin between users"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        service = factories.ServiceFactory.create(
            project=project, offer=offer, effort_hours=10, effort_rate=150
        )
        offer.save()
        factories.LoggedHoursFactory.create(
            service=service,
            rendered_by=self.user,
            rendered_on=dt.date(2026, 9, 10),
            hours=5,
        )
        data = self.get("/api/squeeze/", period="2026-09")
        [user] = data["users"]
        self.assertEqual(user["user"], "ab")
        self.assertEqual(user["hours_in_range"], 5)
        [project_row] = data["projects"]
        self.assertEqual(project_row["project"]["id"], project.id)
        self.assertEqual(list(project_row["users"]), ["ab"])

    @override_settings(
        FEATURES={
            FEATURES.CONTROLLING: F.NEVER,
            FEATURES.PRODUCTIVITY: F.NEVER,
        }
    )
    def test_features(self):
        """The reports require the same features as in the web interface"""
        for url in [
            "/api/projected-gross-margin/",
            "/api/project-budget-statistics/",
            "/api/third-party-costs/",
            "/api/open-items/",
            "/api/hours-per-type/",
            "/api/green-hours/",
            "/api/logging/",
            "/api/squeeze/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        for url in ["/api/hours-per-customer/", "/api/planning-vs-logbook/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(KEY_DATA_API_TOKEN="secret")
    def test_reporting_token(self):
        """The static token is only for key data and cash data"""
        self.client.logout()
        auth = {"Authorization": "Bearer secret"}
        response = self.client.get("/api/key-data/", headers=auth)
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/project-budget-statistics/", headers=auth)
        self.assertEqual(response.status_code, 401)
