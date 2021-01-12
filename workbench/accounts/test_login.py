from django.conf import settings
from django.test import Client, TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts import views
from workbench.accounts.models import User
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
    def tearDown(self):
        deactivate_all()

    def test_login(self):
        """Basic login and logout redirects"""
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
        """The login_hint cookie is removed when logging out explicitly"""
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
        """Exercise the OAuth2 webserver flow implementation"""
        FakeFlow.EMAIL = "user@example.com"
        FakeFlow.RAISE_EXCEPTION = False

        client = Client()
        response = client.get("/accounts/oauth2/")
        self.assertRedirects(
            response, "http://example.com/auth/", fetch_redirect_response=False
        )

        response = client.get("/accounts/oauth2/?code=x", HTTP_ACCEPT_LANGUAGE="en")
        self.assertRedirects(response, "/accounts/login/?error=1")
        self.assertEqual(
            messages(response),
            ["No user with email address user@example.com found."],
        )

        FakeFlow.EMAIL = "user@{}".format(settings.WORKBENCH.SSO_DOMAIN)
        response = client.get("/accounts/oauth2/?code=x", HTTP_ACCEPT_LANGUAGE="en")
        self.assertRedirects(response, "/accounts/update/")
        self.assertEqual(messages(response), ["Welcome! Please fill in your details."])
        response = client.post(
            "/accounts/update/",
            {
                "_full_name": "Test",
                "_short_name": "T",
                "language": "en",
                "working_time_model": factories.WorkingTimeModelFactory.create().pk,
            },
        )
        self.assertEqual(client.cookies.get("login_hint").value, FakeFlow.EMAIL)

        client = Client()
        response = client.get("/accounts/oauth2/?code=x")
        self.assertRedirects(response, "/")
        self.assertEqual(messages(response), [])
        self.assertEqual(client.cookies.get("login_hint").value, FakeFlow.EMAIL)

        # Disabled user
        User.objects.update(is_active=False)
        client = Client()
        FakeFlow.EMAIL = "user@{}".format(settings.WORKBENCH.SSO_DOMAIN)
        response = client.get("/accounts/oauth2/?code=x", HTTP_ACCEPT_LANGUAGE="en")
        self.assertRedirects(response, "/accounts/login/?error=1")
        self.assertEqual(
            messages(response),
            ["The user with email address user@feinheit.ch is inactive."],
        )

        client = Client()
        client.cookies.load({"login_hint": FakeFlow.EMAIL})

        FakeFlow.EMAIL = "user@example.com"
        response = client.get("/accounts/oauth2/?code=x", HTTP_ACCEPT_LANGUAGE="en")
        self.assertRedirects(response, "/accounts/login/?error=1")
        self.assertEqual(
            messages(response), ["No user with email address user@example.com found."]
        )
        # Login hint cookie has been removed when login fails
        self.assertEqual(client.cookies.get("login_hint").value, "")

    def test_server_flow_user_data_failure(self):
        """Failing to fetch user data shouldn't produce an internal server error"""
        FakeFlow.EMAIL = "user@example.com"
        FakeFlow.RAISE_EXCEPTION = True

        response = self.client.get("/accounts/oauth2/?code=x")
        self.assertRedirects(response, "/accounts/login/")
        self.assertEqual(
            messages(response),
            ["Fehler während Abholen der Daten. Bitte nochmals versuchen."],
        )

    def test_accounts_update_404(self):
        """No authentication and no saved email address --> 404"""
        response = self.client.get("/accounts/update/")
        self.assertEqual(response.status_code, 404)

    def test_account_update(self):
        """Users can only update some fields themselves"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        wtm = factories.WorkingTimeModelFactory.create()

        response = self.client.post(
            "/accounts/update/",
            {
                "_full_name": "Test",
                "_short_name": "T",
                "language": "en",
                "working_time_model": wtm.pk,
                "planning_hours_per_day": 6,
            },
        )
        self.assertRedirects(response, "/")

        user.refresh_from_db()
        self.assertEqual(user._short_name, "T")
        self.assertNotEqual(user.working_time_model, wtm)  # Can only be set initially
