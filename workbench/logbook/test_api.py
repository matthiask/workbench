import datetime as dt

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories


class LogbookAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_hours(self):
        """Logged hours can be filtered, the total includes all matches"""
        user = factories.UserFactory.create(_short_name="ab")
        service = factories.ServiceFactory.create(title="Design")
        mine = factories.LoggedHoursFactory.create(
            service=service,
            rendered_by=user,
            rendered_on=dt.date(2026, 10, 1),
            hours=2,
            description="Wireframes",
        )
        other = factories.LoggedHoursFactory.create(
            rendered_on=dt.date(2026, 9, 1), hours="1.5"
        )
        self.client.force_login(user)

        def ids(query=""):
            data = self.client.get(f"/api/logbook/hours/{query}").json()
            return [row["id"] for row in data["items"]]

        data = self.client.get("/api/logbook/hours/").json()
        self.assertEqual(data["total_hours"], "3.5")
        self.assertEqual(data["count"], 2)
        self.assertEqual([row["id"] for row in data["items"]], [mine.pk, other.pk])
        self.assertEqual(data["items"][0]["project"]["code"], service.project.code)
        self.assertEqual(data["items"][0]["service"], "Design")
        self.assertEqual(data["items"][0]["rendered_by"], "ab")

        # Pages of matches, the total and the count include all of them
        data = self.client.get("/api/logbook/hours/?limit=1&offset=1").json()
        self.assertEqual([row["id"] for row in data["items"]], [other.pk])
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["total_hours"], "3.5")
        response = self.client.get("/api/logbook/hours/?limit=10001")
        self.assertEqual(response.status_code, 422)
        response = self.client.get("/api/logbook/hours/?offset=-1")
        self.assertEqual(response.status_code, 422)

        self.assertEqual(ids("?q=wireframes"), [mine.pk])
        self.assertEqual(ids(f"?project={service.project_id}"), [mine.pk])
        self.assertEqual(
            ids(f"?customer={other.service.project.customer_id}"), [other.pk]
        )
        self.assertEqual(ids(f"?service={other.service_id}"), [other.pk])
        offer = factories.OfferFactory.create(project=service.project)
        service.offer = offer
        service.save()
        self.assertEqual(ids(f"?offer={offer.pk}"), [mine.pk])
        self.assertEqual(ids("?rendered_by=AB"), [mine.pk])
        self.assertEqual(ids("?since=2026-09-15"), [mine.pk])
        self.assertEqual(ids("?until=2026-09-15"), [other.pk])

    def test_costs(self):
        """Logged costs can be filtered, the totals include all matches"""
        user = factories.UserFactory.create(_short_name="ab")
        hosting = factories.LoggedCostFactory.create(
            rendered_by=user,
            cost=100,
            third_party_costs=80,
            description="Hosting",
        )
        expense = factories.LoggedCostFactory.create(
            cost=50, are_expenses=True, description="Train ticket"
        )
        self.client.force_login(user)

        def ids(query=""):
            data = self.client.get(f"/api/logbook/costs/{query}").json()
            return {row["id"] for row in data["items"]}

        data = self.client.get("/api/logbook/costs/").json()
        self.assertEqual(data["total_cost"], "150.00")
        self.assertEqual(data["total_third_party_costs"], "80.00")
        self.assertEqual(data["count"], 2)

        self.assertEqual(ids("?q=hosting"), {hosting.pk})
        self.assertEqual(ids("?expenses=true"), {expense.pk})
        self.assertEqual(ids("?rendered_by=AB"), {hosting.pk})
        self.assertEqual(ids(f"?project={expense.service.project_id}"), {expense.pk})
