import datetime as dt
from unittest.mock import ANY

from django.test import TestCase
from django.test.utils import override_settings
from time_machine import travel

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice
from workbench.projects.models import InternalType, Project
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
        url = "/api/reports/hours-per-customer/"
        data = self.get(url, period="2026-Q3")
        self.assertEqual((data["since"], data["until"]), ("2026-07-01", "2026-09-30"))
        data = self.get(url, period="2026-2")
        self.assertEqual((data["since"], data["until"]), ("2026-02-01", "2026-02-28"))
        data = self.get(url, period="2026", until="2026-03-31")
        self.assertEqual((data["since"], data["until"]), ("2026-01-01", "2026-03-31"))
        data = self.get(url)
        self.assertEqual(data["since"], monday().isoformat())

        for period in ["2026-13", "2026-Q5", "last month", "2026-00"]:
            response = self.client.get(url, {"period": period})
            self.assertEqual(response.status_code, 422)
        response = self.client.get(url, {"period": "2026-09", "since": "2026-10-01"})
        self.assertEqual(response.status_code, 422)

    def test_dates_out_of_range(self):
        """Dates far away are validation errors, not crashes"""
        for url, params in [
            ("/api/reports/hours-per-customer/", {"period": "0000"}),
            ("/api/reports/hours-per-customer/", {"period": "9999-12"}),
            ("/api/reports/hours-per-customer/", {"period": "9999-Q4"}),
            ("/api/reports/hours-per-customer/", {"since": "0001-01-01"}),
            ("/api/reports/squeeze/", {"since": "9999-12-20", "until": "9999-12-31"}),
            ("/api/planning/export/", {"since": "9999-12-20", "until": "9999-12-31"}),
            ("/api/reports/key-data/", {"month": "0001-01"}),
            ("/api/reports/working-time/", {"year": "99999"}),
            ("/api/reports/working-time/", {"year": "0"}),
        ]:
            with self.subTest(url=url, params=params):
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, 422, response.content)

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
                data = self.get("/api/reports/hours-per-customer/", period=period)
                self.assertEqual((data["since"], data["until"]), expected)

        data = self.get(
            "/api/reports/hours-per-customer/", period="last-month", since="2026-01-15"
        )
        self.assertEqual(data["since"], "2026-01-15")
        response = self.client.get(
            "/api/reports/hours-per-customer/", {"period": "last-day"}
        )
        self.assertEqual(response.status_code, 422)

    def test_users(self):
        """Users are filtered by short name or team"""
        other = factories.UserFactory.create(_short_name="cd")
        service = factories.ServiceFactory.create()
        for user in [self.user, other]:
            factories.LoggedHoursFactory.create(
                service=service, rendered_by=user, hours=2
            )

        url = "/api/reports/hours-per-customer/"
        self.assertEqual(self.get(url)["total_hours"], "4.0")
        data = self.get(url, user="AB")
        self.assertEqual(data["total_hours"], "2.0")
        self.assertEqual(data["users"], {"ab": "2.0"})
        self.assertEqual(self.get(url, user=["ab", "cd"])["total_hours"], "4.0")

        team = factories.TeamFactory.create(name="Design")
        team.members.add(other)
        self.assertEqual(self.get(url, team="design")["users"], {"cd": "2.0"})

        response = self.client.get(url, {"user": ["ab", "xy"]})
        self.assertEqual(response.status_code, 422)
        self.assertIn("xy", response.content.decode())
        self.assertEqual(self.client.get(url, {"team": "nope"}).status_code, 422)

        # Users have to be in the team
        response = self.client.get(url, {"team": "design", "user": ["ab", "cd"]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["msg"], "Not in the team Design: ab"
        )

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

        data = self.get("/api/reports/hours-per-customer/")
        [customer] = data["customers"]
        self.assertEqual(customer["customer"]["id"], service.project.customer_id)
        self.assertEqual(customer["users"], {"ab": "3.0"})

        data = self.get("/api/reports/hours-per-type/")
        [user] = data["users"]
        self.assertEqual(user["user"], "ab")
        self.assertEqual(user["external"], "3.0")
        self.assertEqual(user["types"][0]["reached_percentage"], "100.0")

        data = self.get("/api/reports/green-hours/")
        self.assertEqual(data["users"][0]["user"], "ab")
        self.assertEqual(data["users"][0]["overdrawn"], "3.0")
        self.assertEqual(data["total"]["total"], "3.0")

        data = self.get("/api/reports/planning-vs-logbook/", user="ab")
        self.assertEqual(data["planned"], "10.0")
        self.assertEqual(data["logged"], "3.0")
        [customer] = data["customers"]
        self.assertEqual(customer["weeks"][0]["week"], monday().isoformat())

        data = self.get("/api/reports/logging/")
        [user] = data["users"]
        self.assertEqual(user["logged_hours"]["sum"], "3.0")
        self.assertIsInstance(user["logging"], str)

        # A team without members means nobody, not everybody
        factories.TeamFactory.create(name="Empty")
        data = self.get("/api/reports/hours-per-customer/", team="empty")
        self.assertEqual(data["total_hours"], "0.0")
        self.assertEqual(
            self.get("/api/reports/hours-per-type/", team="empty")["users"], []
        )
        self.assertEqual(
            self.get("/api/reports/green-hours/", team="empty")["users"], []
        )
        data = self.get("/api/reports/planning-vs-logbook/", team="empty")
        self.assertEqual((data["planned"], data["logged"]), ("0.0", "0.0"))

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

        data = self.get("/api/reports/budget/")
        [row] = data["projects"]
        self.assertEqual(row["project"]["id"], project.id)
        self.assertEqual(row["owned_by"], "ab")
        self.assertEqual(row["effort_cost"], "500.00")
        self.assertEqual(row["delta"], "450.00")
        self.assertEqual(data["overall"]["delta_positive"], "450.00")
        self.assertEqual(
            self.get("/api/reports/budget/", owned_by="AB")["projects"],
            data["projects"],
        )
        self.assertEqual(
            self.get("/api/reports/budget/", internal=True)["projects"], []
        )
        response = self.client.get("/api/reports/budget/", {"owned_by": "xy"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("owned_by", response.content.decode())

        # The cleanup filters look at today's open projects, they don't
        # combine with a cutoff date or the closed projects
        for params in [
            {"filter": "old-projects", "closed": True},
            {"filter": "no-projected-gross-margin", "date": in_days(-30)},
        ]:
            response = self.client.get("/api/reports/budget/", params)
            self.assertEqual(response.status_code, 422, params)
        self.assertEqual(
            self.client.get(
                "/api/reports/budget/",
                {"filter": "old-projects", "date": dt.date.today()},
            ).status_code,
            200,
        )

        # Closed projects are sorted by their closing date, like in the web
        # interface
        closed = []
        for days, hours in [(-20, 10), (-10, 1)]:
            other = factories.ProjectFactory.create(closed_on=in_days(days))
            factories.LoggedHoursFactory.create(
                service=factories.ServiceFactory.create(project=other, effort_rate=100),
                hours=hours,
            )
            closed.append(other.pk)
        data = self.get("/api/reports/budget/", closed=True)
        self.assertEqual(
            [row["project"]["id"] for row in data["projects"]], closed[::-1]
        )

        data = self.get("/api/reports/third-party-costs/")
        [row] = data["projects"]
        self.assertEqual(row["logged"], {"past": "120.00", "future": "0.00"})
        self.assertEqual(data["total_not_invoiced"], "120.00")

        data = self.get("/api/reports/open-items/")
        self.assertEqual(data["total_excl_tax"], "200.00")
        self.assertEqual(data["invoices"][0]["project"]["id"], project.id)
        data = self.get("/api/reports/open-items/", date=in_days(-50).isoformat())
        self.assertEqual(data["invoices"], [])

        data = self.get("/api/reports/projected-gross-margin/")
        month = f"{in_days(30):%Y-%m}"
        # The invoice's gross margin (200 - 120) uses up the projection
        self.assertEqual(data["monthly"], {month: "920.00"})
        self.assertEqual(data["projects"][0]["not_invoiced"], "920.00")

    def test_key_data_month(self):
        """Key data of a given month"""
        self.assertEqual(
            self.get("/api/reports/key-data/", month="2026-01")["month"], "2026-01"
        )
        response = self.client.get("/api/reports/key-data/", {"month": "January"})
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
        data = self.get("/api/reports/squeeze/", period="2026-09")
        [user] = data["users"]
        self.assertEqual(user["user"], "ab")
        self.assertEqual(user["hours_in_range"], "5.0")
        [project_row] = data["projects"]
        self.assertEqual(project_row["project"]["id"], project.id)
        self.assertEqual(list(project_row["users"]), ["ab"])
        self.assertEqual(
            data["outreach"],
            {
                "internal_types": [],
                "users": [],
                "totals": {"hours": "0.0", "deals": "0.00", "deals_per_hour": None},
            },
        )

    def test_squeeze_outreach(self):
        """Squeeze compares hours spent on outreach with accepted deals"""
        outreach = InternalType.objects.create(
            name="Outreach", percentage=10, is_outreach=True
        )
        project = factories.ProjectFactory.create(
            type=Project.INTERNAL, internal_type=outreach
        )
        factories.LoggedHoursFactory.create(
            service=factories.ServiceFactory.create(project=project),
            rendered_by=self.user,
            rendered_on=dt.date(2026, 9, 10),
            hours=4,
        )
        deal = factories.DealFactory.create(
            owned_by=self.user, status=Deal.ACCEPTED, closed_on=dt.date(2026, 9, 20)
        )
        deal.values.create(type=factories.ValueTypeFactory.create(), value=1000)
        deal.save()
        deal.contributions.create(user=self.user, weight=100)

        data = self.get("/api/reports/squeeze/", period="2026-09")
        [user] = data["outreach"]["users"]
        self.assertEqual(user["projects"][0]["project"]["id"], project.id)
        self.assertEqual(user["deals_accepted"][0]["deal"]["id"], deal.id)
        self.assertEqual(
            data["outreach"],
            {
                "internal_types": ["Outreach"],
                "users": [
                    {
                        "user": "ab",
                        "hours": "4.0",
                        "deals": "1000.00",
                        "deals_per_hour": "250.00",
                        "projects": [{"project": ANY, "hours": "4.0"}],
                        "deals_accepted": [{"deal": ANY, "share": "1000.00"}],
                    }
                ],
                "totals": {
                    "hours": "4.0",
                    "deals": "1000.00",
                    "deals_per_hour": "250.00",
                },
            },
        )

    @override_settings(
        FEATURES={
            FEATURES.CONTROLLING: F.NEVER,
            FEATURES.PRODUCTIVITY: F.NEVER,
        }
    )
    def test_features(self):
        """The reports require the same features as in the web interface"""
        for url in [
            "/api/reports/projected-gross-margin/",
            "/api/reports/budget/",
            "/api/reports/third-party-costs/",
            "/api/reports/open-items/",
            "/api/reports/hours-per-type/",
            "/api/reports/green-hours/",
            "/api/reports/logging/",
            "/api/reports/squeeze/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        for url in [
            "/api/reports/hours-per-customer/",
            "/api/reports/planning-vs-logbook/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(
        FEATURES={
            FEATURES.CONTROLLING: F.ALWAYS,
            FEATURES.DEALS: F.NEVER,
            FEATURES.PRODUCTIVITY: F.NEVER,
        },
        KEY_DATA_API_TOKEN="secret",
    )
    def test_key_data_features(self):
        """Key data leave out deals and squeeze without their features, the
        static token gets everything"""
        data = self.get("/api/reports/key-data/")
        self.assertIn("gross_margin", data)
        for key in ["deals_funnel", "accepted_deals", "squeeze_gross_margin"]:
            self.assertNotIn(key, data)

        self.client.logout()
        data = self.client.get(
            "/api/reports/key-data/", headers={"Authorization": "Bearer secret"}
        ).json()
        for key in ["deals_funnel", "accepted_deals", "squeeze_gross_margin"]:
            self.assertIn(key, data)

    @override_settings(KEY_DATA_API_TOKEN="secret")
    def test_reporting_token(self):
        """The static token is only for key data and cash data"""
        self.client.logout()
        auth = {"Authorization": "Bearer secret"}
        response = self.client.get("/api/reports/key-data/", headers=auth)
        self.assertEqual(response.status_code, 200)
        # The old URLs still work for integrations
        for url in ["/api/key-data/", "/api/cash-data/"]:
            response = self.client.get(url, headers=auth)
            self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/reports/budget/", headers=auth)
        self.assertEqual(response.status_code, 401)
