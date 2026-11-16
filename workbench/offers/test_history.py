import datetime as dt

from django.db.models import F
from django.test import TestCase

from workbench import factories
from workbench.accounts.middleware import set_user_name
from workbench.audit.models import LoggedAction
from workbench.offers.history import _ordered_items, offer_states
from workbench.offers.models import Offer, OfferHeading, save_positions
from workbench.projects.models import Service
from workbench.services.models import ServiceType
from workbench.tools.validation import in_days


class OfferHistoryTest(TestCase):
    def save_as(self, user):
        """Changes of another person start a new work session"""
        set_user_name(f"user-{user.id}-{user.get_short_name()}")

    def test_offer_states(self):
        """Earlier states of offers are rebuilt from the audit log"""
        user = factories.UserFactory.create()
        other = factories.UserFactory.create()
        ServiceType.objects.create(title="Consulting", hourly_rate=200, position=1)
        ServiceType.objects.create(title="Programming", hourly_rate=150, position=0)

        self.save_as(user)
        offer = factories.OfferFactory.create(title="Website", owned_by=user)
        project = offer.project
        consulting = factories.ServiceFactory.create(
            project=project,
            offer=offer,
            title="Workshop",
            effort_type="Consulting",
            effort_rate=200,
            effort_hours=5,
            position=10,
        )
        programming = factories.ServiceFactory.create(
            project=project,
            offer=offer,
            title="Contact form",
            effort_type="Programming",
            effort_rate=150,
            effort_hours=10,
            position=20,
        )
        OfferHeading.objects.create(offer=offer, title="Phase 1", position=5)
        offer.save()

        self.save_as(other)
        offer.status = Offer.OFFERED
        offer.offered_on = in_days(0)
        offer.valid_until = in_days(60)
        offer.save()

        self.save_as(user)
        programming.title = "Contact form with captcha"
        programming.save()
        consulting.delete()
        offer.save()

        # Unrelated changes aren't part of the history
        factories.OfferFactory.create()

        states = offer_states(project)
        self.assertEqual(len(states), 3)

        [current] = states[0].offers(project)
        self.assertEqual(current.status, Offer.OFFERED)
        self.assertEqual(
            [str(item) for item in current.history_items],
            ["Phase 1", "Contact form with captcha"],
        )

        [offered] = states[1].offers(project)
        self.assertEqual(offered.status, Offer.OFFERED)
        self.assertEqual(offered.owned_by, user)
        # The offer saved the order, also of the service deleted since
        self.assertEqual(
            [str(item) for item in offered.history_items],
            ["Phase 1", "Workshop", "Contact form"],
        )
        self.assertEqual(offered.total_excl_tax, 2500)

        [created] = states[2].offers(project)
        self.assertEqual(created.status, Offer.IN_PREPARATION)
        self.assertEqual(states[2].changed_offer_ids, {offer.pk})

        # Pages and PDFs
        self.client.force_login(user)
        response = self.client.get(project.urls["offer_history"])
        self.assertContains(response, "Website")
        response = self.client.get(
            f"/projects/{project.pk}/offer-history/{states[1].event_id}/pdf/"
            f"?offer={offer.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")
        response = self.client.get(
            f"/projects/{project.pk}/offer-history/{states[2].event_id}/pdf/"
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(f"/projects/{project.pk}/offer-history/1/pdf/")
        self.assertEqual(response.status_code, 404)

        # Services moved to another project leave the history
        programming.project = factories.ProjectFactory.create()
        programming.offer = None
        Service.objects.filter(pk=programming.pk).update(
            project=programming.project, offer=None
        )
        [current] = offer_states(project)[0].offers(project)
        self.assertEqual([str(item) for item in current.history_items], ["Phase 1"])

    def test_reordered_services(self):
        """Earlier states keep the order of services and headings"""
        user = factories.UserFactory.create()
        other = factories.UserFactory.create()
        self.save_as(user)
        offer = factories.OfferFactory.create(owned_by=user)
        first = factories.ServiceFactory.create(
            project=offer.project, offer=offer, title="First", position=10
        )
        second = factories.ServiceFactory.create(
            project=offer.project, offer=offer, title="Second", position=20
        )
        heading = OfferHeading.objects.create(offer=offer, title="Phase", position=30)
        offer.save()

        self.save_as(other)
        save_positions([heading, second, first])

        states = offer_states(offer.project)
        self.assertEqual(
            [
                [str(item) for item in s.offers(offer.project)[0].history_items]
                for s in states
            ],
            [["Phase", "Second", "First"], ["First", "Second", "Phase"]],
        )

    def test_order_fallback(self):
        """Without saved order, services without known position (deleted
        ones) come last, ordered by the list of service types"""
        ServiceType.objects.create(title="Consulting", hourly_rate=200, position=1)
        ServiceType.objects.create(title="Programming", hourly_rate=150, position=0)
        services = [
            Service(pk=1, title="Known", position=10),
            Service(pk=2, title="Workshop", effort_type="Consulting"),
            Service(pk=3, title="Form", effort_type="Programming"),
        ]
        heading = OfferHeading(pk=1, title="Phase", position=5)
        self.assertEqual(
            [
                str(item)
                for item in _ordered_items(
                    services, [heading], missing={2, 3}, item_order=[]
                )
            ],
            ["Phase", "Known", "Form", "Workshop"],
        )
        # The saved order wins when it knows all items
        self.assertEqual(
            [
                str(item)
                for item in _ordered_items(
                    services,
                    [heading],
                    missing={2, 3},
                    item_order=["s3", "h1", "s2", "s1"],
                )
            ],
            ["Form", "Phase", "Workshop", "Known"],
        )

    def test_work_sessions(self):
        """Changes of one person form one state until they pause for more
        than half an hour"""
        user = factories.UserFactory.create()
        self.save_as(user)
        offer = factories.OfferFactory.create(owned_by=user, title="First")

        def ago(minutes):
            LoggedAction.objects.filter(table_name="offers_offer").update(
                created_at=F("created_at") - dt.timedelta(minutes=minutes)
            )

        ago(20)
        offer.title = "Second"
        offer.save()
        self.assertEqual(len(offer_states(offer.project)), 1)

        ago(40)
        offer.title = "Third"
        offer.save()
        states = offer_states(offer.project)
        self.assertEqual(
            [s.offers(offer.project)[0].title for s in states], ["Third", "Second"]
        )

    def test_backfilled_item_order(self):
        """Filling in the order of existing offers isn't a work session"""
        user = factories.UserFactory.create()
        self.save_as(user)
        offer = factories.OfferFactory.create(owned_by=user)

        set_user_name("")
        Offer.objects.filter(pk=offer.pk).update(item_order=["s1"])
        self.assertEqual(len(offer_states(offer.project)), 1)
