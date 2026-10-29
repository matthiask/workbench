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

        data = self.client.get("/api/deals/").json()
        self.assertEqual([d["id"] for d in data], [deal.pk, declined.pk])
        self.assertEqual(data[0]["value"], "5000.00")
        self.assertEqual(data[0]["values"], [{"type": "Design", "value": "5000.00"}])
        self.assertEqual(data[0]["owned_by"], "ab")

        def ids(query):
            return [d["id"] for d in self.client.get(f"/api/deals/{query}").json()]

        self.assertEqual(ids("?status=open"), [deal.pk])
        self.assertEqual(ids("?owned_by=AB"), [deal.pk])
        self.assertEqual(ids(f"?customer={declined.customer_id}"), [declined.pk])
        self.assertEqual(ids("?q=relaunch"), [deal.pk])

        data = self.client.get(f"/api/deals/{deal.pk}/").json()
        self.assertEqual(data["code"], deal.code)

    @override_settings(FEATURES={FEATURES.DEALS: F.NEVER})
    def test_feature(self):
        """Deals require the deals feature"""
        self.client.force_login(factories.UserFactory.create())
        self.assertEqual(self.client.get("/api/deals/").status_code, 403)
