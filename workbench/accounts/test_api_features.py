from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F


class APIFeaturesTest(TestCase):
    def tearDown(self):
        deactivate_all()

    @override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER})
    def test_controlling(self):
        """The API requires the same features as the web interface"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        invoice = factories.InvoiceFactory.create(project=project)
        self.client.force_login(project.owned_by)

        for method, url in [
            ("get", f"/api/projects/{project.pk}/offers/context/"),
            ("post", f"/api/projects/{project.pk}/offers/"),
            ("get", "/api/offers/"),
            ("get", f"/api/offers/{offer.pk}/"),
            ("put", f"/api/offers/{offer.pk}/"),
            ("get", f"/api/projects/stats/?ids={project.pk}"),
            ("get", "/api/invoices/"),
            ("post", "/api/invoices/"),
            ("get", "/api/recurring-invoices/"),
            ("get", f"/api/invoices/{invoice.pk}/"),
            ("get", f"/api/invoices/{invoice.pk}/pdf/"),
            ("get", f"/api/offers/{offer.pk}/pdf/"),
            ("get", "/api/reports/key-data/"),
            ("get", "/api/reports/cash-data/"),
        ]:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(
                    url, {}, content_type="application/json"
                )
                self.assertEqual(response.status_code, 403)

        # Not restricted
        for url in [
            "/api/projects/",
            f"/api/projects/{project.pk}/",
            f"/api/projects/{project.pk}/planning/context/",
            "/api/contacts/organizations/",
            "/api/logbook/hours/",
            "/api/absences/",
            "/api/services/",
            "/api/me/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_projected_gross_margin(self):
        """Projected invoices require the feature of their web view"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        url = "/api/projected-invoices/"
        with override_settings(
            FEATURES={
                FEATURES.CONTROLLING: F.ALWAYS,
                FEATURES.PROJECTED_GROSS_MARGIN: F.NEVER,
            }
        ):
            self.assertEqual(self.client.get(url).status_code, 403)
        with override_settings(
            FEATURES={
                FEATURES.CONTROLLING: F.NEVER,
                FEATURES.PROJECTED_GROSS_MARGIN: F.ALWAYS,
            }
        ):
            self.assertEqual(self.client.get(url).status_code, 200)
