import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.audit.models import LoggedAction
from workbench.offers.models import Offer
from workbench.tools.formats import local_date_format
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code, messages


class OffersTest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_factories(self):
        offer = factories.OfferFactory.create()

        self.client.force_login(offer.owned_by)
        self.client.get(offer.project.urls["detail"])

    def test_create_offer(self):
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
        offer.save()
        project.description = "Test"
        project.save()

        response = self.client.get(project.urls["offers_pdf"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "application/pdf")

    def test_update_offer(self):
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
        offer = factories.OfferFactory.create()
        self.client.force_login(factories.UserFactory.create())

        code = check_code(self, "/offers/")
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
        offer = factories.OfferFactory.create()
        self.client.force_login(offer.owned_by)

        self.assertRedirects(
            self.client.get("/offers/{}/".format(offer.id)),
            "{}#offer{}".format(offer.project.get_absolute_url(), offer.id),
        )

    def test_create_message(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/offers/create/")
        self.assertRedirects(response, "/offers/")
        self.assertEqual(
            messages(response),
            [
                "Offers can only be created from projects. Go to the project"
                " and add services first, then you'll be able to create the offer"
                " itself."
            ],
        )

    def test_status(self):
        today = dt.date.today()
        self.assertEqual(
            Offer(status=Offer.IN_PREPARATION).pretty_status,
            "In preparation since {}".format(local_date_format(today)),
        )
        self.assertEqual(
            Offer(status=Offer.OFFERED, offered_on=today).pretty_status,
            "Offered on {}".format(local_date_format(today)),
        )
        self.assertEqual(
            Offer(status=Offer.DECLINED, closed_on=today).pretty_status,
            "Declined on {}".format(local_date_format(today)),
        )
        self.assertEqual(Offer(status="42").pretty_status, "42")

    def test_declined_offer(self):
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
        offer = factories.OfferFactory.create()
        factories.ServiceFactory.create(project=offer.project, offer=offer)

        self.client.force_login(offer.owned_by)
        response = self.client.get(offer.urls["copy"])
        self.assertContains(
            response, 'data-autocomplete-url="/projects/autocomplete/?only_open=on"'
        )

        response = self.client.post(
            offer.urls["copy"], {"modal-project": offer.project.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a different project as target.")

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
        offer = factories.OfferFactory.create()
        gs = offer.project.grouped_services

        self.assertEqual(gs["offers"][0][0], offer)
        self.assertEqual(gs["offers"][0][1]["services"], [])

    def test_offer_deletion_without_logbook(self):
        offer = factories.OfferFactory.create()
        self.client.force_login(offer.owned_by)

        response = self.client.get(offer.urls["delete"])
        self.assertContains(response, "delete_services")

        response = self.client.post(offer.urls["delete"], {"delete_services": "on"})
        self.assertRedirects(response, offer.project.urls["detail"])

        self.assertEqual(offer.project.services.count(), 0)

    def test_offer_deletion_with_logbook(self):
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

        # Offer should only have updated once (because of skip_related_model)
        actions = LoggedAction.objects.for_model(offer).with_data(id=offer.id)
        self.assertEqual([action.action for action in actions], ["I", "U"])

    def test_offer_pricing_with_flat_rate(self):
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
                "offered_on": dt.date.today().isoformat(),
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
                "offered_on": dt.date.today().isoformat(),
                "status": Offer.DECLINED,
                WarningsForm.ignore_warnings_id: "yes-please-decline",
            },
        )
        self.assertRedirects(
            response, offer.get_absolute_url(), fetch_redirect_response=False
        )

        offer.refresh_from_db()
        self.assertEqual(
            messages(response),
            [
                "All offers of project {} are declined. You might "
                "want to close the project now?".format(offer.project),
                "Offer '{}' has been updated successfully.".format(offer),
            ],
        )
