from django.test import TestCase

from workbench import factories
from workbench.invoices.models import Invoice


class InvoicesTest(TestCase):
    def test_factories(self):
        invoice = factories.InvoiceFactory.create()

        self.client.force_login(invoice.owned_by)
        self.client.get(invoice.urls.url("detail"))

        response = self.client.post(invoice.urls.url("delete"))
        self.assertRedirects(
            response, invoice.urls.url("list"), fetch_redirect_response=False
        )

    def test_create_service_invoice_from_offer(self):
        service = factories.ServiceFactory.create(cost=100)

        self.client.force_login(service.project.owned_by)
        url = service.project.urls.url("createinvoice") + "?type=services&source=offer"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            {
                "contact": service.project.contact_id,
                "title": service.project.title,
                "owned_by": service.project.owned_by_id,
                "discount": "0",
                "liable_to_vat": "1",
                "postal_address": "Anything",
                "selected_services": [service.pk],
            },
        )

        invoice = Invoice.objects.get()
        self.assertRedirects(response, invoice.urls.url("update"))
        self.assertEqual(invoice.subtotal, 100)
