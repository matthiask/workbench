from django.conf import settings
from django.test import Client, TestCase

from workbench import factories
from workbench.accounts import views
from workbench.tools.testing import messages


class FakeFlow:
    EMAIL = "user@example.com"
    RAISE_EXCEPTION = False

    def get_authentication_url(self):
        return "http://example.com/auth/"

    def get_user_data(self):
        if self.RAISE_EXCEPTION:
            raise Exception("Email not verified")
        return {"email": self.EMAIL}


views.GoogleOAuth2Client = lambda *a, **kw: FakeFlow()


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
        FakeFlow.RAISE_EXCEPTION = False

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
        self.assertRedirects(
            response, "/accounts/login/?login_hint=&prompt=select_account"
        )
        self.assertEqual(
            messages(response),
            ["Keinen Benutzer mit Emailadresse user@example.com gefunden."],
        )
        # Login hint cookie has been removed when login fails
        self.assertEqual(client.cookies.get("login_hint").value, "")

    def test_server_flow_user_data_failure(self):
        FakeFlow.EMAIL = "user@example.com"
        FakeFlow.RAISE_EXCEPTION = True

        response = self.client.get("/accounts/oauth2/?code=x")
        self.assertRedirects(response, "/accounts/login/")
        self.assertEqual(
            messages(response),
            ["Fehler während Abholen der Nutzerdaten. Bitte nochmals versuchen."],
        )
