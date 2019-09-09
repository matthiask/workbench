from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.offers.models import Offer
from workbench.tools.formats import local_date_format
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import messages


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

        offer.offered_on = date.today()
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
        self.assertRedirects(response, offer.project.urls["detail"])

        response = self.client.get(offer.urls["delete"])
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                "services": [service.id],
                # "offered_on": date.today().isoformat(),
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
                "postal_address": "Anything",
                "services": [service.id],
                "offered_on": date.today().isoformat(),
                "status": Offer.ACCEPTED,
            },
        )
        self.assertRedirects(response, offer.project.urls["detail"])

        offer.refresh_from_db()
        self.assertEqual(offer.closed_on, date.today())
        self.assertAlmostEqual(offer.subtotal, Decimal("2000"))

        response = self.client.get(offer.urls["delete"])
        self.assertRedirects(response, offer.project.urls["detail"])
        self.assertEqual(
            messages(response), ["Offers in preparation may be deleted, others not."]
        )

        response = self.client.get(service.urls["detail"])
        self.assertRedirects(response, offer.project.urls["detail"])

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
            messages(response), ["service 'Any service' has been updated successfully."]
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
                "postal_address": "Anything",
                "services": [service.id],
                "offered_on": date.today().isoformat(),
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
                "postal_address": "Anything",
                "services": [service.id],
                "offered_on": date.today().isoformat(),
                "status": Offer.IN_PREPARATION,
                WarningsForm.ignore_warnings_id: "status-change-but-already-closed",
            },
        )
        self.assertRedirects(response, offer.project.urls["detail"])

        offer.refresh_from_db()
        self.assertIsNone(offer.closed_on)

    def test_list(self):
        factories.OfferFactory.create()
        self.client.force_login(factories.UserFactory.create())

        def valid(p):
            self.assertEqual(self.client.get("/offers/?" + p).status_code, 200)

        valid("")
        valid("s=all")
        valid("s=10")
        valid("s=20")

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
        today = date.today()
        self.assertEqual(
            Offer(status=Offer.IN_PREPARATION).pretty_status,
            "In preparation since {}".format(local_date_format(today)),
        )
        self.assertEqual(
            Offer(status=Offer.OFFERED, offered_on=today).pretty_status,
            "Offered on {}".format(local_date_format(today)),
        )
        self.assertEqual(
            Offer(status=Offer.REJECTED, closed_on=today).pretty_status,
            "Rejected on {}".format(local_date_format(today)),
        )
        self.assertEqual(Offer(status="42").pretty_status, "42")

    def test_offer_rejection(self):
        project = factories.ProjectFactory.create()

        offer1 = factories.OfferFactory.create(project=project, status=Offer.REJECTED)
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

        project = factories.ProjectFactory.create()
        response = self.client.post(offer.urls["copy"], {"project-project": project.pk})
        self.assertEqual(response.status_code, 299)
        self.assertEqual(response.json(), {"redirect": project.get_absolute_url()})

        self.assertEqual(project.offers.count(), 1)
        self.assertEqual(project.services.count(), 1)
