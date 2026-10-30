import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.deals.models import Deal, Value


class DealsAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_deals(self):
        """Deals can be listed and filtered"""
        user = factories.UserFactory.create(_short_name="ab")
        deal = factories.DealFactory.create(
            title="Relaunch", owned_by=user, decision_expected_on=dt.date(2026, 12, 1)
        )
        Value.objects.create(
            deal=deal,
            type=factories.ValueTypeFactory.create(title="Design"),
            value=5000,
        )
        deal.save()
        declined = factories.DealFactory.create(status=Deal.DECLINED)
        self.client.force_login(user)

        data = self.client.get("/api/deals/").json()["items"]
        self.assertEqual([d["id"] for d in data], [deal.pk, declined.pk])
        self.assertEqual(data[0]["value"], "5000.00")
        self.assertEqual(data[0]["values"], [{"type": "Design", "value": "5000.00"}])
        self.assertEqual(data[0]["owned_by"], "ab")

        def ids(query):
            return [
                d["id"] for d in self.client.get(f"/api/deals/{query}").json()["items"]
            ]

        self.assertEqual(ids("?status=open"), [deal.pk])
        self.assertEqual(ids("?owned_by=AB"), [deal.pk])
        self.assertEqual(ids(f"?customer={declined.customer_id}"), [declined.pk])
        self.assertEqual(ids("?q=relaunch"), [deal.pk])

        data = self.client.get(f"/api/deals/{deal.pk}/").json()
        self.assertEqual(data["code"], deal.code)

    def test_stats(self):
        """Accepted and declined deals of a period, and their history"""
        user = factories.UserFactory.create(_short_name="ab")
        accepted = factories.DealFactory.create(title="Relaunch", owned_by=user)
        Value.objects.create(
            deal=accepted,
            type=factories.ValueTypeFactory.create(title="Design"),
            value=5000,
        )
        accepted.contributions.create(user=user)
        accepted.status = Deal.ACCEPTED
        accepted.closed_on = dt.date.today()
        accepted.save()
        declined = factories.DealFactory.create(
            status=Deal.DECLINED,
            closed_on=dt.date.today(),
            closing_type=factories.ClosingTypeFactory.create(title="Too expensive"),
        )
        self.client.force_login(user)

        data = self.client.get("/api/deals/stats/").json()
        self.assertEqual(data["accepted"]["sum"], 5000)
        self.assertEqual(
            data["accepted"]["by_user"], [{"user": "ab", "count": 1, "sum": 5000}]
        )
        self.assertEqual(data["accepted"]["by_value_type"][0]["type"], "Design")
        self.assertEqual(data["accepted"]["deals"][0]["id"], accepted.pk)
        self.assertEqual(data["declined"]["deals"][0]["id"], declined.pk)
        self.assertEqual(
            data["declined"]["by_closing_type"],
            {"Too expensive": {"count": 1, "sum": 0}},
        )

        data = self.client.get("/api/deals/stats/", {"user": "ab"}).json()
        self.assertEqual(data["accepted"]["count"], 1)
        self.assertEqual(data["declined"]["deals"], [])
        data = self.client.get("/api/deals/stats/", {"period": "2020"}).json()
        self.assertEqual(data["accepted"]["deals"], [])

        data = self.client.get("/api/deals/history/").json()
        relaunch = [c for c in data["changes"] if c["deal"]["id"] == accepted.pk]
        self.assertTrue(relaunch)
        self.assertTrue(
            any("Relaunch" in text for c in relaunch for text in c["changes"])
        )

    @override_settings(FEATURES={FEATURES.DEALS: F.NEVER})
    def test_feature(self):
        """Deals require the deals feature"""
        self.client.force_login(factories.UserFactory.create())
        self.assertEqual(self.client.get("/api/deals/").status_code, 403)
        self.assertEqual(self.client.get("/api/deals/stats/").status_code, 403)
        self.assertEqual(self.client.get("/api/deals/history/").status_code, 403)
        response = self.client.post("/api/deals/", {}, content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_create(self):
        """Deals are created like in the web interface"""
        user = factories.UserFactory.create(_short_name="ab")
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        factories.ValueTypeFactory.create(title="Design")
        group = factories.AttributeGroupFactory.create(title="Source")
        group.attributes.create(title="Referral")
        self.client.force_login(user)

        deal = {
            "title": "Relaunch",
            "contact": person.pk,
            "probability": "normal",
            "values": {"design": 5000},
            "attributes": {"Source": "referral"},
        }
        response = self.client.post(
            "/api/deals/?dry_run=true", deal, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], None)
        self.assertEqual(response.json()["value"], "5000.00")
        self.assertFalse(Deal.objects.exists())

        response = self.client.post(
            "/api/deals/", deal, content_type="application/json"
        )
        created = Deal.objects.get()
        self.assertEqual(response.json()["code"], created.code)
        self.assertEqual(created.customer, person.organization)
        self.assertEqual(created.owned_by, user)
        self.assertEqual(created.value, 5000)
        self.assertEqual([a.title for a in created.attributes.all()], ["Referral"])
        self.assertEqual(created.contributions.get().user, user)

    def test_create_errors(self):
        """Unknown value types and missing attributes list the choices"""
        group = factories.AttributeGroupFactory.create(title="Source")
        group.attributes.create(title="Referral")
        customer = factories.OrganizationFactory.create()
        self.client.force_login(factories.UserFactory.create())

        response = self.client.post(
            "/api/deals/",
            {
                "title": "Relaunch",
                "customer": customer.pk,
                "probability": "high",
                "values": {"Nope": 100},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [(e["loc"][2:], e["msg"]) for e in response.json()["detail"]],
            [
                (["values", "Nope"], "Unknown value type. Choices: "),
                (
                    ["attributes", "Source"],
                    "This field is required. Choices: 'Referral'",
                ),
            ],
        )

        # Errors of the form
        response = self.client.post(
            "/api/deals/",
            {
                "title": "Relaunch",
                "customer": customer.pk,
                "probability": "high",
                "attributes": {"Source": "Referral"},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"][2:], ["decision_expected_on"]
        )
        self.assertFalse(Deal.objects.exists())
