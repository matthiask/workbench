from decimal import Decimal

from django.test import TestCase

from workbench import factories
from workbench.offers.models import Offer


class OffersTest(TestCase):
    def test_factories(self):
        offer = factories.OfferFactory.create()

        self.client.force_login(offer.owned_by)
        self.client.get(offer.project.urls.url("services"))

    def test_create_offer(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        service = factories.ServiceFactory.create(
            project=project, effort_type="Programming", effort_rate=200, effort_hours=10
        )

        url = project.urls.url("createoffer")
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
            },
        )

        offer = Offer.objects.get()
        self.assertRedirects(response, offer.get_absolute_url())
        self.assertAlmostEqual(offer.total_excl_tax, Decimal("2000"))
        self.assertAlmostEqual(offer.total, Decimal("2154"))
