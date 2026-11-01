import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.tools.validation import in_days
from workbench.views import NEEDS_ACTION_SHOWN


class NeedsActionTest(TestCase):
    @override_settings(FEATURES={FEATURES.DEALS: F.ALWAYS})
    def test_long_categories(self):
        """Long categories show their first entries, the others on request"""
        user = factories.UserFactory.create()
        deals = [
            factories.DealFactory.create(owned_by=user, title=f"Deal {i}")
            for i in range(NEEDS_ACTION_SHOWN + 2)
        ]
        self.client.force_login(user)

        response = self.client.get("/")
        self.assertContains(response, "Show 2 more")
        self.assertContains(response, "wb-more", count=2)
        for deal in deals:
            self.assertContains(response, deal.get_absolute_url())

        # "Show 1 more" would take as much space as the entry itself
        deals[0].delete()
        response = self.client.get("/")
        self.assertNotContains(response, "wb-more")
        self.assertContains(response, deals[-1].get_absolute_url())

    def test_offers(self):
        """Offers in preparation on closed projects can't lead anywhere, the
        others are sorted by what needs to be done first"""
        user = factories.UserFactory.create()
        closed = factories.OfferFactory.create(owned_by=user)
        closed.project.closed_on = dt.date.today()
        closed.project.save()
        preparing = factories.OfferFactory.create(owned_by=user)
        expired = factories.OfferFactory.create(
            owned_by=user,
            status=Offer.OFFERED,
            offered_on=in_days(-60),
            valid_until=in_days(-30),
        )
        valid = factories.OfferFactory.create(
            owned_by=user,
            status=Offer.OFFERED,
            offered_on=in_days(-10),
            valid_until=in_days(20),
        )

        self.assertEqual(
            list(Offer.objects.maybe_actionable(user=user)),
            [expired, valid, preparing],
        )

    def test_order(self):
        """Deals by their expected decision, invoices overdue first"""
        user = factories.UserFactory.create()
        overdue = factories.DealFactory.create(
            owned_by=user, decision_expected_on=in_days(-10)
        )
        later = factories.DealFactory.create(
            owned_by=user, decision_expected_on=in_days(30)
        )
        newer = factories.DealFactory.create(
            owned_by=user, decision_expected_on=in_days(10)
        )
        self.assertEqual(
            list(Deal.objects.maybe_actionable(user=user)), [overdue, newer, later]
        )

        sent = factories.InvoiceFactory.create(
            owned_by=user,
            status=Invoice.SENT,
            invoiced_on=in_days(-60),
            due_on=in_days(-30),
        )
        # Invoices in preparation have a due date too
        preparing = factories.InvoiceFactory.create(
            owned_by=user, invoiced_on=in_days(-90), due_on=in_days(-60)
        )
        self.assertEqual(
            list(Invoice.objects.maybe_actionable(user=user)), [sent, preparing]
        )
