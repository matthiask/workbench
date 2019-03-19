from django.test import TestCase

from workbench import factories


class InvoicesTest(TestCase):
    def test_factories(self):
        invoice = factories.InvoiceFactory.create()

        self.client.force_login(invoice.owned_by)
        self.client.get(invoice.urls.url("detail"))

        response = self.client.post(invoice.urls.url("delete"))
        self.assertRedirects(
            response, invoice.urls.url("list"), fetch_redirect_response=False
        )
