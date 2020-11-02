import datetime as dt
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils.translation import deactivate_all

from time_machine import travel

from workbench import factories
from workbench.audit.models import LoggedAction
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.formats import local_date_format
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code, messages
from workbench.tools.validation import in_days


class OffersTest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_create_offer(self):
        """Create an offer and generate a PDF"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        service = factories.ServiceFactory.create(
            project=project, effort_type="Programming", effort_rate=200, effort_hours=10
        )

        url = project.urls["createoffer"]
        response = self.client.get(url)
        self.assertContains(response, 'id="id_postal_address"')
        self.assertNotContains(response, 'data-field-value="')
        postal_address = factories.PostalAddressFactory.create(person=project.contact)
        response = self.client.get(url)
        self.assertContains(response, 'id="id_postal_address"')
        self.assertContains(response, 'data-field-value="')

        response = self.client.post(
            url,
            {
                "title": "Stuff",
                "owned_by": project.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": postal_address.postal_address,
                "services": [service.id],
                "status": Offer.IN_PREPARATION,
            },
        )
        self.assertEqual(response.status_code, 302)

        offer = Offer.objects.get()
        self.assertRedirects(response, offer.get_absolute_url())
        self.assertAlmostEqual(offer.total_excl_tax, Decimal("1990"))
        self.assertAlmostEqual(offer.total, Decimal("2143.25"))

        pdf = self.client.get(offer.urls["pdf"])
        self.assertEqual(pdf.status_code, 200)  # No crash
        self.assertEqual(pdf["content-type"], "application/pdf")

        offer.show_service_details = True
        offer.save()

        pdf = self.client.get(offer.urls["pdf"])
        self.assertEqual(pdf.status_code, 200)  # No crash
        self.assertEqual(pdf["content-type"], "application/pdf")

        # Deleting the service automagically updates the offer
        offer.services.get().delete()
        offer.refresh_from_db()
        self.assertAlmostEqual(offer.total_excl_tax, Decimal("-10"))

        pdf = self.client.get(offer.urls["pdf"])
        self.assertEqual(pdf.status_code, 200)  # No crash
        self.assertEqual(pdf["content-type"], "application/pdf")

    def test_offers_pdf(self):
        """Generate a PDF containing several offers"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["offers_pdf"])
        self.assertRedirects(response, project.get_absolute_url())
        self.assertEqual(messages(response), ["No offers in project."])

        offer = factories.OfferFactory.create(project=project)

        response = self.client.get(project.urls["offers_pdf"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

        offer.offered_on = dt.date.today()
        offer.valid_until = in_days(60)
        offer.save()
        project.description = "Test"
        project.save()

        response = self.client.get(project.urls["offers_pdf"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

    def test_update_offer(self):
        """Offer and bound services update warnings and errors"""
        offer = factories.OfferFactory.create(title="Test")
        service = factories.ServiceFactory.create(
            project=offer.project,
            effort_type="Programming",
            effort_rate=200,
            effort_hours=10,
        )
        self.client.force_login(offer.owned_by)

        response = self.client.get(service.urls["update"])
        self.assertRedirects(response, service.get_absolute_url())

        response = self.client.get(offer.urls["delete"])
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything\nStreet\nCity",
                "services": [service.id],
                # "offered_on": dt.date.today().isoformat(),
                "status": Offer.ACCEPTED,
            },
        )
        self.assertContains(response, "Offered on date missing for selected state.")
        self.assertContains(response, "Valid until date missing for selected state.")

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything\nStreet\nCity",
                "services": [service.id],
                "offered_on": dt.date.today().isoformat(),
                "valid_until": in_days(60).isoformat(),
                "status": Offer.ACCEPTED,
            },
        )
        self.assertRedirects(response, offer.get_absolute_url())

        response = self.client.get(offer.urls["update"])
        self.assertContains(
            response,
            "This offer is not in preparation anymore. I assume you know what you",
        )

        offer.refresh_from_db()
        self.assertEqual(offer.closed_on, dt.date.today())
        self.assertAlmostEqual(offer.subtotal, Decimal("2000"))

        response = self.client.get(service.urls["detail"])
        self.assertRedirects(
            response, "%s#service%s" % (offer.project.urls["detail"], service.pk)
        )

        response = self.client.get(
            service.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            "Most fields are disabled because service is bound"
            " to an offer which is not in preparation anymore.",
        )

        self.assertTrue(service.allow_logging)
        response = self.client.post(
            service.urls["update"],
            {
                "allow_logging": False,
                WarningsForm.ignore_warnings_id: "no-role-selected",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)
        service.refresh_from_db()
        self.assertFalse(service.allow_logging)
        self.assertEqual(
            messages(response), ["Service 'Any service' has been updated successfully."]
        )
        self.assertEqual(service.offer, offer)

        response = self.client.get(
            service.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            "Cannot delete a service bound to an offer"
            " which is not in preparation anymore.",
        )

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything\nStreet\nCity",
                "services": [service.id],
                "offered_on": dt.date.today().isoformat(),
                "status": Offer.IN_PREPARATION,
            },
        )
        self.assertContains(response, "but the offer")

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything\nStreet\nCity",
                "services": [service.id],
                "offered_on": dt.date.today().isoformat(),
                "status": Offer.IN_PREPARATION,
                WarningsForm.ignore_warnings_id: "status-change-but-already-closed",
            },
        )
        self.assertRedirects(response, offer.get_absolute_url())

        offer.refresh_from_db()
        self.assertIsNone(offer.closed_on)

    def test_list(self):
        """Filter form smoke test"""
        offer = factories.OfferFactory.create()
        self.client.force_login(factories.UserFactory.create())

        code = check_code(self, Offer.urls["list"])
        code("")
        code("q=test")
        code("s=all")
        code("s=10")
        code("s=20")
        code("s=20")
        code("org={}".format(offer.project.customer_id))
        code("owned_by={}".format(offer.owned_by_id))
        code("owned_by=-1")  # mine
        code("owned_by=0")  # only inactive

    def test_detail(self):
        """The detail URL of offers redirects to the project detail page anchor"""
        offer = factories.OfferFactory.create()
        self.client.force_login(offer.owned_by)

        self.assertRedirects(
            self.client.get("{}{}/".format(Offer.urls["list"], offer.id)),
            "{}#offer{}".format(offer.project.get_absolute_url(), offer.id),
        )

    def test_create_message(self):
        """Attempting to directly create an offer only produces a help message"""
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get(Offer.urls["create"])
        self.assertRedirects(response, Offer.urls["list"])
        self.assertEqual(
            messages(response),
            [
                "Offers can only be created from projects. Go to the project"
                " and add services first, then you'll be able to create the offer"
                " itself."
            ],
        )

    def test_status(self):
        """Offer status badge"""
        project = factories.ProjectFactory.create()
        today = dt.date.today()
        self.assertEqual(
            Offer(project=project, status=Offer.IN_PREPARATION).pretty_status,
            "In preparation since {}".format(local_date_format(today)),
        )
        self.assertEqual(
            Offer(
                project=project,
                status=Offer.OFFERED,
                offered_on=today,
                valid_until=today,
            ).pretty_status,
            "Offered on {}".format(local_date_format(today)),
        )
        self.assertEqual(
            Offer(
                project=project, status=Offer.DECLINED, closed_on=today
            ).pretty_status,
            "Declined on {}".format(local_date_format(today)),
        )
        self.assertEqual(Offer(project=project, status="42").pretty_status, "42")

    def test_declined_offer(self):
        """Declined offers' services do not allow logging and are not part of
        service hours"""
        project = factories.ProjectFactory.create()

        offer1 = factories.OfferFactory.create(project=project, status=Offer.DECLINED)
        offer2 = factories.OfferFactory.create(project=project)

        factories.ServiceFactory.create(project=project, offer=offer1, effort_hours=10)
        factories.ServiceFactory.create(project=project, offer=offer2, effort_hours=20)
        factories.ServiceFactory.create(project=project, effort_hours=40)

        gs = project.grouped_services
        self.assertEqual([offer2, None, offer1], [row[0] for row in gs["offers"]])
        self.assertEqual(gs["service_hours"], Decimal("60.00"))  # Not 70

        self.assertEqual(project.services.logging().count(), 2)

    def test_offer_copying(self):
        """Offers can be copied to different projects"""
        offer = factories.OfferFactory.create()
        factories.ServiceFactory.create(project=offer.project, offer=offer)

        self.client.force_login(offer.owned_by)
        response = self.client.get(offer.urls["copy"])
        self.assertContains(
            response,
            'data-autocomplete-url="{}?only_open=on"'.format(
                Project.urls["autocomplete"]
            ),
        )

        response = self.client.post(
            offer.urls["copy"], {"modal-project": offer.project.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="same-project"')

        project = factories.ProjectFactory.create()
        response = self.client.post(offer.urls["copy"], {"modal-project": project.pk})
        self.assertEqual(response.status_code, 299)
        offer = project.offers.first()
        self.assertEqual(
            response.json(),
            {"redirect": "%s#offer%s" % (project.get_absolute_url(), offer.pk)},
        )

        self.assertEqual(project.offers.count(), 1)
        self.assertEqual(project.services.count(), 1)

    def test_postal_address_validation(self):
        """Postal addresses are validated (a bit)"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        url = project.urls["createoffer"]
        response = self.client.post(
            url,
            {
                "title": "Stuff",
                "owned_by": project.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                "status": Offer.IN_PREPARATION,
            },
        )
        self.assertContains(response, 'value="short-postal-address"')

    def test_grouped_services_empty_offers(self):
        """Offers without services still appear in Project.grouped_services"""
        offer = factories.OfferFactory.create()
        gs = offer.project.grouped_services

        self.assertEqual(gs["offers"][0][0], offer)
        self.assertEqual(gs["offers"][0][1]["services"], [])

    def test_offer_deletion_without_logbook(self):
        """Offers without linked logged hours can be deleted, including all services"""
        offer = factories.OfferFactory.create()
        self.client.force_login(offer.owned_by)

        response = self.client.get(offer.urls["delete"])
        self.assertContains(response, "delete_services")

        response = self.client.post(offer.urls["delete"], {"delete_services": "on"})
        self.assertRedirects(response, offer.project.urls["detail"])

        self.assertEqual(offer.project.services.count(), 0)

    def test_offer_deletion_with_logbook(self):
        """Offers with some linked logged hours can be deleted, but the service stays"""
        offer = factories.OfferFactory.create()
        self.client.force_login(offer.owned_by)
        service = factories.ServiceFactory.create(project=offer.project, offer=offer)
        factories.LoggedHoursFactory.create(service=service)

        response = self.client.get(offer.urls["delete"])
        self.assertNotContains(response, "delete_services")

        response = self.client.post(offer.urls["delete"], {"delete_services": "on"})
        self.assertRedirects(response, offer.project.urls["detail"])

        self.assertEqual(offer.project.services.count(), 1)

    def test_offer_pricing(self):
        """Offer total calculation works"""
        offer = factories.OfferFactory.create()
        service = factories.ServiceFactory.create(offer=offer, project=offer.project)

        self.client.force_login(offer.owned_by)
        response = self.client.get(offer.urls["pricing"])
        self.assertContains(response, "data-effort-rate", 2)  # Empty form too

        response = self.client.post(
            offer.urls["pricing"],
            {
                "discount": 100,
                "liable_to_vat": "on",
                "services-TOTAL_FORMS": 1,
                "services-INITIAL_FORMS": 1,
                "services-MAX_NUM_FORMS": 1000,
                "services-0-id": service.id,
                "services-0-offer": offer.id,
                "services-0-title": service.title,
                "services-0-effort_type": "Programming",
                "services-0-effort_rate": 250,
                "services-0-effort_hours": 10,
                "services-0-cost": 35,
            },
        )

        self.assertRedirects(response, offer.get_absolute_url())

        offer.refresh_from_db()
        service.refresh_from_db()

        self.assertEqual(service.service_cost, 250 * 10 + 35)
        self.assertEqual(offer.total_excl_tax, 250 * 10 + 35 - 100)

        # Offer has been
        # - inserted
        # - updated once because of _fts
        # - updated only once because of skip_related_model
        actions = LoggedAction.objects.for_model(offer).with_data(id=offer.id)
        self.assertEqual([action.action for action in actions], ["I", "U", "U"])

    def test_offer_pricing_with_flat_rate(self):
        """Pricing with flat rates does not allow editing effort rates"""
        project = factories.ProjectFactory.create(flat_rate=160)
        offer = factories.OfferFactory.create(project=project)
        factories.ServiceFactory.create(offer=offer, project=project)

        self.client.force_login(project.owned_by)
        response = self.client.get(offer.urls["pricing"])
        self.assertContains(
            response,
            '<input type="number" name="services-0-effort_rate" step="0.01" class="form-control" disabled id="id_services-0-effort_rate">',  # noqa
            html=True,
        )

    def test_renumber_offers(self):
        """Offers can be renumbered (and reordered)"""
        project = factories.ProjectFactory.create()
        offer1 = factories.OfferFactory.create(project=project)
        offer2 = factories.OfferFactory.create(project=project)
        field1 = "offer_{}_code".format(offer1.pk)
        field2 = "offer_{}_code".format(offer2.pk)

        self.client.force_login(project.owned_by)
        response = self.client.get(project.urls["renumber_offers"])
        self.assertContains(response, field1)
        self.assertContains(response, field2)

        response = self.client.post(
            project.urls["renumber_offers"], {field1: 1, field2: 1}
        )
        self.assertContains(response, "Codes must be unique")

        response = self.client.post(
            project.urls["renumber_offers"], {field1: 4, field2: 3}
        )
        self.assertRedirects(response, project.urls["detail"])

        offer1.refresh_from_db()
        offer2.refresh_from_db()

        self.assertEqual(offer1._code, 4)
        self.assertEqual(offer2._code, 3)

    def test_please_decline(self):
        """Please do not decline offers but update them and send them again"""
        offer = factories.OfferFactory.create()
        self.client.force_login(offer.owned_by)

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything\nStreet\nCity",
                "offered_on": in_days(0).isoformat(),
                "valid_until": in_days(60).isoformat(),
                "status": Offer.DECLINED,
            },
        )
        self.assertContains(
            response,
            "However, if you just want to change a few things and send the offer",
        )

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything\nStreet\nCity",
                "offered_on": in_days(0).isoformat(),
                "valid_until": in_days(60).isoformat(),
                "status": Offer.DECLINED,
                WarningsForm.ignore_warnings_id: "yes-please-decline",
            },
        )
        self.assertRedirects(
            response, offer.get_absolute_url(), fetch_redirect_response=False
        )

        offer.refresh_from_db()  # Refresh the offer title etc.
        self.assertEqual(
            messages(response),
            [
                "All offers of project {} are declined. You might "
                "want to close the project now?".format(offer.project),
                "Offer '{}' has been updated successfully.".format(offer),
            ],
        )

        offer.project.closed_on = dt.date.today()
        self.assertIsNone(offer.project.solely_declined_offers_warning(request=None))

    @travel("2020-04-21 12:00")
    def test_offer_with_closed_project(self):
        """Sent offers on closed projects have a warning badge"""
        project = factories.ProjectFactory.create(closed_on=dt.date.today())
        offer = factories.OfferFactory.create(
            project=project, offered_on=dt.date.today(), status=Offer.OFFERED
        )

        self.assertEqual(
            offer.status_badge,
            '<span class="badge badge-warning">Offered on 21.04.2020, but project closed on 21.04.2020</span>',  # noqa
        )

    @travel("2020-05-04 12:00")
    def test_offer_not_valid_anymore(self):
        """Sent offers which are not valid anymore have a warning badge"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(
            project=project,
            offered_on=in_days(-90),
            valid_until=in_days(-30),
            status=Offer.OFFERED,
        )

        self.assertEqual(
            offer.status_badge,
            '<span class="badge badge-warning">Offered on 04.02.2020, but not valid anymore</span>',  # noqa
        )

    def test_offers_ordering(self):
        """The ordering of offers is: Valid offers, not offered yet, declined offers"""
        project = factories.ProjectFactory.create()

        declined = factories.OfferFactory.create(
            project=project, offered_on=dt.date.today(), status=Offer.DECLINED
        )
        accepted = factories.OfferFactory.create(
            project=project, offered_on=dt.date.today(), status=Offer.ACCEPTED
        )
        in_preparation = factories.OfferFactory.create(project=project)
        factories.ServiceFactory.create(project=project)

        self.assertTrue(accepted < in_preparation)  # _code
        self.assertTrue(in_preparation < None)
        self.assertTrue(None < declined)
        self.assertTrue(in_preparation < declined)

        self.assertEqual(
            [row[0] for row in project.grouped_services["offers"]],
            [accepted, in_preparation, None, declined],
        )
        self.assertEqual(in_preparation < 42, 0)

    def test_model_validation(self):
        """Offer model validation"""
        offer = Offer(
            title="Test",
            project=factories.ProjectFactory.create(),
            owned_by=factories.UserFactory.create(),
            status=Offer.OFFERED,
            postal_address="Test\nStreet\nCity",
            _code=1,
        )

        with self.assertRaises(ValidationError) as cm:
            offer.clean_fields()
        self.assertEqual(
            list(cm.exception),
            [
                ("offered_on", ["Offered on date missing for selected state."]),
                ("valid_until", ["Valid until date missing for selected state."]),
            ],
        )

        with self.assertRaises(ValidationError) as cm:
            offer.offered_on = in_days(0)
            offer.valid_until = in_days(-1)
            offer.full_clean()
        self.assertEqual(
            list(cm.exception),
            [("valid_until", ["Valid until date has to be after offered on date."])],
        )

    def test_properties(self):
        """Offer property testing"""
        self.assertTrue(Offer(status=Offer.ACCEPTED).is_accepted)
        self.assertTrue(Offer(status=Offer.DECLINED).is_declined)
