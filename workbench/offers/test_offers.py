from datetime import date
from decimal import Decimal

from django.test import TestCase

from workbench import factories
from workbench.offers.models import Offer
from workbench.tools.formats import local_date_format
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import messages


class OffersTest(TestCase):
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
        postal_address = factories.PostalAddressFactory.create(person=project.contact)
        response = self.client.get(url)
        self.assertNotContains(response, 'id="id_postal_address"')

        response = self.client.post(
            url,
            {
                "title": "Stuff",
                "owned_by": project.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "pa": postal_address.id,
                "services": [service.id],
                "status": Offer.IN_PREPARATION,
            },
        )
        self.assertEqual(response.status_code, 302)

        offer = Offer.objects.get()
        self.assertRedirects(response, offer.get_absolute_url())
        self.assertAlmostEqual(offer.total_excl_tax, Decimal("2000"))
        self.assertAlmostEqual(offer.total, Decimal("2154"))

        pdf = self.client.get(offer.urls["pdf"])
        self.assertEqual(pdf.status_code, 200)  # No crash

        # Deleting the service automagically updates the offer
        offer.services.get().delete()
        offer.refresh_from_db()
        self.assertAlmostEqual(offer.total_excl_tax, Decimal("0"))

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
                # "pa": postal_address.id,
                "services": [service.id],
                # "offered_on": local_date_format(date.today()),
                "status": Offer.ACCEPTED,
            },
        )
        self.assertContains(response, "Offertdatum fehlt für den ausgewählten Status.")

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                # "pa": postal_address.id,
                "services": [service.id],
                "offered_on": local_date_format(date.today()),
                "status": Offer.ACCEPTED,
            },
        )
        self.assertRedirects(response, offer.project.urls["detail"])

        offer.refresh_from_db()
        self.assertEqual(offer.closed_on, date.today())

        response = self.client.get(offer.urls["delete"])
        self.assertRedirects(response, offer.project.urls["detail"])
        self.assertEqual(
            messages(response),
            ["Offerten in Vorbereitung können gelöscht werden, andere nicht."],
        )

        response = self.client.get(service.urls["detail"])
        self.assertRedirects(response, offer.project.urls["detail"])

        response = self.client.get(
            service.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            "Die meisten Felder sind gesperrt weil die Leistung mit einer Offerte"
            " verbunden ist, welche sich nicht mehr in Vorbereitung befindet.",
        )

        response = self.client.get(
            service.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            "Kann Leistung von Offerte, welche nicht mehr in Vorbereitung ist,"
            " nicht mehr bearbeiten.",
        )

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                # "pa": postal_address.id,
                "services": [service.id],
                "offered_on": local_date_format(date.today()),
                "status": Offer.IN_PREPARATION,
            },
        )
        self.assertContains(response, "aber die Offerte")

        response = self.client.post(
            offer.urls["update"],
            {
                "title": "Stuff",
                "owned_by": offer.owned_by_id,
                "discount": "10",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                # "pa": postal_address.id,
                "services": [service.id],
                "offered_on": local_date_format(date.today()),
                "status": Offer.IN_PREPARATION,
                WarningsForm.ignore_warnings_id: "on",
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
                "Offerten können nur aus Projekten erstellt werden. Gehe"
                " zuerst zum Projekt, füge Leistungen hinzu, und dann kannst"
                " Du die eigentliche Offerte erstellen."
            ],
        )
