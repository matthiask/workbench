from django.test import TestCase

from workbench import factories


class RedirectsTest(TestCase):
    def test_redirects(self):
        """Root redirects work correctly"""
        self.client.force_login(factories.UserFactory.create())

        response = self.client.get("/projects/projects/42/")
        self.assertRedirects(response, "/projects/42/", fetch_redirect_response=False)

        response = self.client.get("/offers/42/")
        self.assertRedirects(
            response, "/projects/offers/42/", fetch_redirect_response=False
        )
