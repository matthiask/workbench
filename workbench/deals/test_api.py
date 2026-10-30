import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.deals.models import Deal, Value
from workbench.offers.models import Offer
from workbench.tools.validation import in_days


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
        # Open deals by their expected decision, closed deals by closing date
        declined.closed_on = dt.date(2026, 11, 15)
        declined.save()
        self.assertEqual(ids("?period=2026-11"), [declined.pk])
        self.assertEqual(ids("?since=2026-11-20"), [deal.pk])

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
        self.assertEqual(data["accepted"]["sum"], "5000.00")
        self.assertEqual(
            data["accepted"]["by_user"], [{"user": "ab", "count": 1, "sum": "5000.00"}]
        )
        self.assertEqual(data["accepted"]["by_value_type"][0]["type"], "Design")
        self.assertEqual(data["accepted"]["deals"][0]["id"], accepted.pk)
        self.assertEqual(data["declined"]["deals"][0]["id"], declined.pk)
        self.assertEqual(
            data["declined"]["by_closing_type"],
            {"Too expensive": {"count": 1, "sum": "0.00"}},
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

    def test_update(self):
        """Deals are changed field by field like in the web interface"""
        user = factories.UserFactory.create(_short_name="ab")
        design = factories.ValueTypeFactory.create(title="Design")
        hosting = factories.ValueTypeFactory.create(title="Hosting")
        deal = factories.DealFactory.create(
            owned_by=user, title="Relaunch", probability=Deal.NORMAL
        )
        Value.objects.create(deal=deal, type=design, value=5000)
        Value.objects.create(deal=deal, type=hosting, value=1000)
        deal.contributions.create(user=user, weight=100)
        deal.save()
        self.client.force_login(user)
        url = f"/api/deals/{deal.pk}/"

        def patch(data, query=""):
            return self.client.patch(
                f"{url}{query}", data, content_type="application/json"
            )

        response = patch({"title": "Website"}, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Website")
        deal.refresh_from_db()
        self.assertEqual(deal.title, "Relaunch")

        response = patch({"values": {"design": 6000, "Hosting": None}})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["values"], [{"type": "Design", "value": "6000.00"}]
        )
        deal.refresh_from_db()
        self.assertEqual((deal.title, deal.value), ("Relaunch", 6000))
        # Contributions stay as they were
        self.assertEqual(list(deal.contributors.all()), [user])

        response = patch({"probability": "high", "decision_expected_on": None})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [["body", "data", "decision_expected_on"]],
        )
        response = patch({"owned_by": "nobody", "values": {"Nope": 1}})
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]],
            [["body", "data", "owned_by"], ["body", "data", "values", "Nope"]],
        )

    def test_status(self):
        """Deals are closed and reopened, their offers accepted or declined"""
        user = factories.UserFactory.create()
        deal = factories.DealFactory.create(owned_by=user, probability=Deal.NORMAL)
        offer = factories.OfferFactory.create(
            title="Relaunch",
            postal_address="Customer\nStreet\nCity",
            status=Offer.OFFERED,
            offered_on=dt.date.today(),
            valid_until=in_days(30),
        )
        deal.related_offers.add(offer)
        factories.ClosingTypeFactory.create(title="Won", represents_a_win=True)
        factories.ClosingTypeFactory.create(title="Too expensive")
        self.client.force_login(user)
        url = f"/api/deals/{deal.pk}/status/"

        def post(data, query=""):
            return self.client.post(
                f"{url}{query}", data, content_type="application/json"
            )

        response = post({"status": "accepted", "closing_type": "Too expensive"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("'Won'", response.content.decode())

        response = post({"status": "accepted", "closing_type": "won"}, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "Accepted")
        deal.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual((deal.status, offer.status), (Deal.OPEN, Offer.OFFERED))

        response = post({"status": "accepted", "closing_type": "won", "offers": []})
        self.assertEqual(response.status_code, 200, response.content)
        deal.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual((deal.status, offer.status), (Deal.ACCEPTED, Offer.OFFERED))
        self.assertEqual(deal.closed_on, dt.date.today())

        response = post({"status": "open"})
        deal.refresh_from_db()
        self.assertEqual((deal.status, deal.closed_on), (Deal.OPEN, None))

        response = post({
            "status": "declined",
            "closing_type": "Too expensive",
            "closing_notice": "Cheaper offer",
        })
        self.assertEqual(response.status_code, 200, response.content)
        deal.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual((deal.status, offer.status), (Deal.DECLINED, Offer.DECLINED))
        self.assertEqual(deal.closing_notice, "Cheaper offer")
