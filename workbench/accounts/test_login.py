import types

from django.conf import settings
from django.contrib.messages import get_messages
from django.test import Client, TestCase

from workbench import factories
from workbench.accounts import views


def messages(response):
    return [m.message for m in get_messages(response.wsgi_request)]


class FakeFlow:
    EMAIL = "user@example.com"
    EMAIL_VERIFIED = True

    def step1_get_authorize_url(self):
        return "http://example.com/auth/"

    def step2_exchange(self, code):
        return types.SimpleNamespace(
            id_token={"email_verified": self.EMAIL_VERIFIED, "email": self.EMAIL}
        )


views.oauth2_flow = lambda *a, **kw: FakeFlow()


class LoginTestCase(TestCase):
    def test_login(self):
        user = factories.UserFactory.create()

        self.assertRedirects(self.client.get("/"), "/accounts/login/")
        self.assertRedirects(self.client.get("/accounts/"), "/accounts/login/")

        self.client.login(email=user.email)

        self.assertContains(
            self.client.get("/"), 'href="/accounts/logout/"', 1, status_code=200
        )
        self.assertRedirects(self.client.get("/accounts/"), "/accounts/update/")
        self.assertRedirects(self.client.get("/accounts/login/"), "/")

    def test_login_hint_removal_on_logout(self):
        user = factories.UserFactory.create()
        self.client.login(email=user.email)
        self.client.cookies.load({"login_hint": "test@example.com"})

        self.assertEqual(
            self.client.cookies.get("login_hint").value, "test@example.com"
        )
        response = self.client.get("/accounts/logout/")
        self.assertRedirects(response, "/accounts/login/")

        self.assertEqual(self.client.cookies.get("login_hint").value, "")

    def test_server_flow(self):
        FakeFlow.EMAIL = "user@example.com"
        FakeFlow.EMAIL_VERIFIED = True

        client = Client()
        response = client.get("/accounts/oauth2/")
        self.assertRedirects(
            response, "http://example.com/auth/", fetch_redirect_response=False
        )

        response = client.get("/accounts/oauth2/?code=x")
        self.assertRedirects(response, "/accounts/login/")
        self.assertEqual(
            messages(response),
            ["Keinen Benutzer mit Emailadresse user@example.com gefunden."],
        )

        FakeFlow.EMAIL = "user@{}".format(settings.WORKBENCH.SSO_DOMAIN)
        response = client.get("/accounts/oauth2/?code=x")
        self.assertRedirects(response, "/accounts/update/")
        self.assertEqual(
            messages(response), ["Willkommen! Bitte fülle das folgende Formular aus."]
        )
        self.assertEqual(client.cookies.get("login_hint").value, FakeFlow.EMAIL)

        client = Client()
        response = client.get("/accounts/oauth2/?code=x")
        self.assertRedirects(response, "/")
        self.assertEqual(messages(response), [])
        self.assertEqual(client.cookies.get("login_hint").value, FakeFlow.EMAIL)

        client = Client()
        client.cookies.load({"login_hint": FakeFlow.EMAIL})

        FakeFlow.EMAIL = "user@example.com"
        response = client.get("/accounts/oauth2/?code=x")
        self.assertRedirects(response, "/accounts/login/")
        self.assertEqual(
            messages(response),
            ["Keinen Benutzer mit Emailadresse user@example.com gefunden."],
        )
        # Login hint cookie has been removed when login fails
        self.assertEqual(client.cookies.get("login_hint").value, "")

    def test_server_flow_email_not_verified(self):
        FakeFlow.EMAIL = "user@example.com"
        FakeFlow.EMAIL_VERIFIED = False

        response = self.client.get("/accounts/oauth2/?code=x")
        self.assertRedirects(response, "/accounts/login/")
        self.assertEqual(messages(response), ["Konnte Emailadresse nicht bestimmen."])
