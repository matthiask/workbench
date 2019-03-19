from django.test import TestCase

from workbench import factories


class LoginTestCase(TestCase):
    def test_login(self):
        user = factories.UserFactory.create()

        self.assertRedirects(self.client.get("/"), "/accounts/login/")

        self.client.login(email=user.email)

        self.assertContains(
            self.client.get("/"), 'href="/accounts/logout/"', 1, status_code=200
        )

    def test_login_hint_removal(self):
        user = factories.UserFactory.create()
        self.client.login(email=user.email)
        self.client.cookies.load({"login_hint": "test@example.com"})

        self.assertEqual(
            self.client.cookies.get("login_hint").value, "test@example.com"
        )
        response = self.client.get("/accounts/logout/")
        self.assertRedirects(response, "/accounts/login/")

        self.assertEqual(self.client.cookies.get("login_hint").value, "")
