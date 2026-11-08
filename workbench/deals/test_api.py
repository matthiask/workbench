import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.models import APIToken
from workbench.deals.models import AttributeGroup, Deal, Value
from workbench.offers.models import Offer
from workbench.tools.validation import in_days, monday


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
        declined.contributions.create(user=user, weight=100)
        self.assertEqual(ids("?status=declined&contributor=AB"), [declined.pk])
        self.assertEqual(ids("?status=open&contributor=AB"), [])
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
        self.assertEqual(list(created.contributors.all()), [user])

        # Deals created for others: the owner contributes
        other = factories.UserFactory.create(_short_name="cd")
        response = self.client.post(
            "/api/deals/", deal | {"owned_by": "cd"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        created = Deal.objects.get(pk=response.json()["id"])
        self.assertEqual(list(created.contributors.all()), [other])

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

    def test_update_ignore_warnings(self):
        """Warnings of the web interface are errors unless ignored"""
        deal = factories.DealFactory.create(contact=None, probability=Deal.NORMAL)
        deal.contributions.create(user=deal.owned_by, weight=100)
        self.client.force_login(deal.owned_by)
        url = f"/api/deals/{deal.pk}/"

        response = self.client.patch(
            url, {"probability": "low"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["msg"], "No contact selected.")

        response = self.client.patch(
            f"{url}?ignore_warnings=no-contact",
            {"probability": "low"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        deal.refresh_from_db()
        self.assertEqual(deal.probability, Deal.LOW)

    def test_update_with_default_probability(self):
        """Deals with the default probability can be updated without
        choosing one"""
        deal = factories.DealFactory.create()
        self.client.force_login(deal.owned_by)
        response = self.client.patch(
            f"/api/deals/{deal.pk}/",
            {"title": "Renamed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["probability"], "normal")

    def test_update_archived_value_types_and_attributes(self):
        """Values of archived value types and attributes of archived groups
        which the deal has can be changed and removed, like in the web form"""
        deal = factories.DealFactory.create()
        old = factories.ValueTypeFactory.create(title="Old", is_archived=True)
        deal.values.create(type=old, value=500)
        group = AttributeGroup.objects.create(title="Gone", is_archived=True)
        fax = group.attributes.create(title="Fax", is_archived=True)
        phone = group.attributes.create(title="Phone")
        deal.attributes.add(fax)
        self.client.force_login(deal.owned_by)

        response = self.client.patch(
            f"/api/deals/{deal.pk}/",
            {"values": {"old": 800}, "attributes": {"gone": "fax"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(deal.values.get().value, 800)

        response = self.client.patch(
            f"/api/deals/{deal.pk}/",
            {"values": {"old": None}, "attributes": {"gone": "phone"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(deal.values.exists())
        self.assertEqual(list(deal.attributes.all()), [phone])

        # Other deals don't get them
        other = factories.DealFactory.create(owned_by=deal.owned_by)
        response = self.client.patch(
            f"/api/deals/{other.pk}/",
            {"values": {"old": 100}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_value_types_and_attributes(self):
        """Value types and attribute groups are listed with the titles the
        other endpoints take, archived ones are left out"""
        design = factories.ValueTypeFactory.create(title="Design", position=1)
        factories.ValueTypeFactory.create(title="Old", is_archived=True)
        group = AttributeGroup.objects.create(title="Source", is_required=True)
        referral = group.attributes.create(title="Referral")
        group.attributes.create(title="Fax", is_archived=True)
        AttributeGroup.objects.create(title="Gone", is_archived=True)
        self.client.force_login(factories.UserFactory.create())

        self.assertEqual(
            self.client.get("/api/deals/value-types/").json(),
            [{"id": design.pk, "title": "Design"}],
        )
        won = factories.ClosingTypeFactory.create(title="Won", represents_a_win=True)
        self.assertEqual(
            self.client.get("/api/deals/closing-types/").json(),
            [{"id": won.pk, "title": "Won", "represents_a_win": True}],
        )
        self.assertEqual(
            self.client.get("/api/deals/attributes/").json(),
            [
                {
                    "id": group.pk,
                    "title": "Source",
                    "is_required": True,
                    "attributes": [{"id": referral.pk, "title": "Referral"}],
                }
            ],
        )

    def test_update_contributions(self):
        """Contributions are changed by the short names of the users, a
        new owner takes over the contribution of the old owner unless
        contributions are given too"""
        owner = factories.UserFactory.create(_short_name="ab")
        other = factories.UserFactory.create(_short_name="cd")
        deal = factories.DealFactory.create(owned_by=owner)
        deal.contributions.create(user=owner, weight=100)
        self.client.force_login(owner)
        url = f"/api/deals/{deal.pk}/"

        def patch(data):
            return self.client.patch(url, data, content_type="application/json")

        response = patch({"owned_by": "cd"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["contributions"], [{"user": "cd", "weight": 100}]
        )
        response = patch({"owned_by": "ab", "contributions": {"ab": 50}})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["contributions"],
            [{"user": "ab", "weight": 50}, {"user": "cd", "weight": 100}],
        )
        response = patch({"owned_by": "cd"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["contributions"], [{"user": "cd", "weight": 100}]
        )

        response = patch({"contributions": {"AB": 0, "cd": 50}})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["contributions"], [{"user": "cd", "weight": 50}]
        )

        # The owner has to contribute, unknown users are errors
        response = patch({"contributions": {"cd": 0}})
        self.assertEqual(response.status_code, 422)
        response = patch({"contributions": {"xy": 50}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "contributions", "xy"]
        )
        response = patch({"contributions": {"ab": 30}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            dict(deal.contributions.values_list("user", "weight")), {other.pk: 50}
        )

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

        # A new owner takes over the contribution
        factories.UserFactory.create(_short_name="cd")
        response = patch({"owned_by": "cd"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(sorted(u._short_name for u in deal.contributors.all()), ["cd"])
        response = patch({"owned_by": "ab"})
        self.assertEqual(response.status_code, 200, response.content)

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

    def test_decline_without_offers_and_planned_work(self):
        """Declining a deal without declining its offers doesn't ask about
        their planned work"""
        user = factories.UserFactory.create()
        deal = factories.DealFactory.create(owned_by=user)
        offer = factories.OfferFactory.create(
            title="Relaunch",
            postal_address="Customer\nStreet\nCity",
            status=Offer.OFFERED,
            offered_on=dt.date.today(),
            valid_until=in_days(30),
        )
        deal.related_offers.add(offer)
        factories.PlannedWorkFactory.create(
            project=offer.project, offer=offer, weeks=[monday(in_days(14))]
        )
        factories.ClosingTypeFactory.create(title="Too expensive")
        self.client.force_login(user)
        url = f"/api/deals/{deal.pk}/status/"

        response = self.client.post(
            url,
            {"status": "declined", "closing_type": "Too expensive", "offers": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        # Declining the offer asks
        self.client.post(url, {"status": "open"}, content_type="application/json")
        response = self.client.post(
            url,
            {"status": "declined", "closing_type": "Too expensive"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("delete_planned_work", response.content.decode())

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
        self.assertEqual(response.json()["status"], "accepted")
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

    def test_status_offers_without_related_offers(self):
        """Offers given when closing a deal without related offers are an
        error, not ignored"""
        user = factories.UserFactory.create()
        deal = factories.DealFactory.create(owned_by=user, probability=Deal.NORMAL)
        offer = factories.OfferFactory.create(status=Offer.OFFERED)
        factories.ClosingTypeFactory.create(title="Won", represents_a_win=True)
        self.client.force_login(user)

        response = self.client.post(
            f"/api/deals/{deal.pk}/status/",
            {"status": "accepted", "closing_type": "Won", "offers": [offer.pk]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "offers"]
        )
        deal.refresh_from_db()
        self.assertEqual(deal.status, Deal.OPEN)

    def test_related_offers(self):
        """Offers are linked to open deals and unlinked like in the web
        interface, by ID or code"""
        user = factories.UserFactory.create()
        offer = factories.OfferFactory.create(status=Offer.OFFERED)
        deal = factories.DealFactory.create(
            owned_by=user, customer=offer.project.customer
        )
        self.client.force_login(user)
        url = f"/api/deals/{deal.pk}/offers/"

        def post(path, data, query=""):
            return self.client.post(
                f"{path}{query}", data, content_type="application/json"
            )

        def errors(response):
            self.assertEqual(response.status_code, 422)
            return [(e["loc"][2:], e["msg"]) for e in response.json()["detail"]]

        response = post(url, {"offers": [offer.code]}, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            [o["code"] for o in response.json()["related_offers"]], [offer.code]
        )
        self.assertFalse(deal.related_offers.exists())

        response = post(url, {"offers": [offer.code.upper()]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(deal.related_offers.get(), offer)

        response = post(url, {"offers": [offer.pk, "nope", 0]})
        self.assertEqual(
            errors(response),
            [
                (
                    ["offers", 0],
                    f"The offer {offer.code} is already linked to this deal.",
                ),
                (
                    ["offers", 1],
                    (
                        "Unknown offer 'nope', expected an ID or a code like"
                        " 2026-0179-o02."
                    ),
                ),
                (
                    ["offers", 2],
                    "Unknown offer 0, expected an ID or a code like 2026-0179-o02.",
                ),
            ],
        )

        # Closed offers are settled
        declined = factories.OfferFactory.create(
            project=offer.project, status=Offer.DECLINED
        )
        response = post(url, {"offers": [declined.pk]})
        self.assertIn("is Declined, only offers", errors(response)[0][1])

        # Offers of other customers are a warning, nothing is saved before
        other = factories.OfferFactory.create()
        response = post(url, {"offers": [other.pk]})
        self.assertEqual(
            errors(response),
            [
                (
                    ["offers", 0],
                    (
                        f"The offer {other.code} belongs to a project of"
                        f" {other.project.customer}, not of the deal's customer"
                        f" {deal.customer}."
                    ),
                )
            ],
        )
        response = post(f"{url}?ignore_warnings=other-customer", {"offers": [other.pk]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(set(deal.related_offers.all()), {offer, other})

        remove = f"{url}remove/"
        response = post(remove, {"offers": [other.code]}, "?dry_run=true")
        self.assertEqual(
            [o["code"] for o in response.json()["related_offers"]], [offer.code]
        )
        self.assertEqual(deal.related_offers.count(), 2)
        response = post(remove, {"offers": [other.code, other.pk]})
        self.assertEqual(
            [o["code"] for o in response.json()["related_offers"]], [offer.code]
        )
        response = post(remove, {"offers": [other.code]})
        self.assertEqual(
            errors(response),
            [(["offers", 0], f"The offer {other.code} isn't linked to this deal.")],
        )

        # Only open deals
        deal.status = Deal.ACCEPTED
        deal.save()
        for path in [url, remove]:
            response = post(path, {"offers": [offer.pk, declined.pk]})
            self.assertEqual(
                errors(response),
                [
                    (
                        [],
                        (
                            "Offers can only be linked to and unlinked from open"
                            " deals, reopen the deal first."
                        ),
                    )
                ],
            )

        self.assertEqual(post(url, {"offers": []}).status_code, 422)
        for value in ["²", 10**20]:
            response = post(url, {"offers": [value]})
            self.assertIn("Unknown offer", errors(response)[0][1])
        self.assertEqual(
            post("/api/deals/0/offers/", {"offers": [offer.pk]}).status_code, 404
        )

    def test_related_offers_read_only(self):
        """Read only tokens can't link offers, not even in dry runs"""
        offer = factories.OfferFactory.create()
        deal = factories.DealFactory.create(customer=offer.project.customer)
        _token, secret = APIToken.create_for(
            user=deal.owned_by, title="CLI", access="read"
        )
        response = self.client.post(
            f"/api/deals/{deal.pk}/offers/?dry_run=true",
            {"offers": [offer.pk]},
            content_type="application/json",
            headers={"authorization": f"Bearer {secret}"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(deal.related_offers.exists())
