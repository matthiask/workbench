from django.test import Client, TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.models import APIToken
from workbench.audit.models import LoggedAction


class APITokenTest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_bearer_auth(self):
        """Personal API tokens authenticate as their active user"""
        project = factories.ProjectFactory.create()
        user = factories.UserFactory.create()
        token, secret = APIToken.create_for(user=user, title="CLI")
        self.assertNotIn(secret, token.key_hash)

        url = f"/api/projects/{project.pk}/planning/context/"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(
            self.client.get(
                url, headers={"authorization": "Bearer wb_nope"}
            ).status_code,
            401,
        )

        response = self.client.get(url, headers={"authorization": f"Bearer {secret}"})
        self.assertEqual(response.status_code, 200)
        token.refresh_from_db()
        self.assertIsNotNone(token.last_used_at)

        # The reporting API accepts tokens of users with the controlling feature
        self.assertEqual(
            self.client.get(
                "/api/reports/cash-data/", headers={"authorization": f"Bearer {secret}"}
            ).status_code,
            200,
        )

        user.is_active = False
        user.save()
        self.assertEqual(
            self.client.get(
                url, headers={"authorization": f"Bearer {secret}"}
            ).status_code,
            401,
        )

    def test_bearer_auth_without_csrf(self):
        """Token authenticated requests do not need a CSRF token"""
        project = factories.ProjectFactory.create()
        _token, secret = APIToken.create_for(user=project.owned_by, title="CLI")

        client = Client(enforce_csrf_checks=True)
        response = client.post(
            f"/api/projects/{project.pk}/planning/import/?dry_run=true",
            {},
            content_type="application/json",
            headers={"authorization": f"Bearer {secret}"},
        )
        self.assertEqual(response.status_code, 200)

    def test_me(self):
        """The authenticated user"""
        user = factories.UserFactory.create(_short_name="ab", _full_name="A B")
        _token, secret = APIToken.create_for(user=user, title="CLI")

        self.assertEqual(self.client.get("/api/me/").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/me/", headers={"authorization": f"Bearer {secret}"}
            ).json(),
            {
                "id": user.pk,
                "short_name": "ab",
                "full_name": "A B",
                "email": user.email,
                "url": "http://testserver/",
            },
        )

    def test_token_page(self):
        """Users create and delete their own tokens"""
        user = factories.UserFactory.create()
        other, _secret = APIToken.create_for(
            user=factories.UserFactory.create(), title="Other"
        )

        response = self.client.get("/accounts/api-tokens/")
        self.assertEqual(response.status_code, 302)

        self.client.force_login(user)
        response = self.client.post("/accounts/api-tokens/", {"title": "Laptop"})
        token = user.api_tokens.get()
        self.assertEqual(token.title, "Laptop")
        self.assertContains(response, "wb_")
        self.assertNotContains(response, "Other")

        self.client.post("/accounts/api-tokens/", {"delete": other.pk})
        self.assertTrue(APIToken.objects.filter(pk=other.pk).exists())

        self.client.post("/accounts/api-tokens/", {"delete": token.pk})
        self.assertFalse(user.api_tokens.exists())

    def test_admin(self):
        """Admins can revoke tokens, but not create or change them"""
        token, _secret = APIToken.create_for(
            user=factories.UserFactory.create(), title="Laptop"
        )
        self.client.force_login(factories.UserFactory.create(is_admin=True))

        response = self.client.get("/admin/accounts/apitoken/")
        self.assertContains(response, "Laptop")
        self.assertEqual(
            self.client.get("/admin/accounts/apitoken/add/").status_code, 403
        )

        response = self.client.post(
            f"/admin/accounts/apitoken/{token.pk}/delete/", {"post": "yes"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(APIToken.objects.exists())

    def test_inactive_session(self):
        """Sessions of deactivated users do not work anymore"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/me/").status_code, 200)

        user.is_active = False
        user.save()
        self.assertEqual(self.client.get("/api/me/").status_code, 401)

    def test_expiry(self):
        """Tokens expire, creating a token removes the user's expired tokens"""
        user = factories.UserFactory.create()
        token, secret = APIToken.create_for(user=user, title="CLI")
        headers = {"authorization": f"Bearer {secret}"}
        self.assertEqual(self.client.get("/api/me/", headers=headers).status_code, 200)

        token.expires_at = timezone.now()
        token.save()
        self.assertEqual(self.client.get("/api/me/", headers=headers).status_code, 401)

        APIToken.create_for(user=user, title="New")
        self.assertEqual(list(user.api_tokens.values_list("title", flat=True)), ["New"])

    def test_cli_login(self):
        """The CLI is authorized through the browser"""
        url = "/cli-login/?port=8123&state=abcdefghijklmnop&name=laptop"

        response = self.client.get(url)
        self.assertRedirects(
            response, "/accounts/login/", fetch_redirect_response=False
        )

        user = factories.UserFactory.create()
        self.client.force_login(user)
        self.assertContains(self.client.get(url), "laptop")
        for invalid in [
            "/cli-login/",
            "/cli-login/?port=80&state=abcdefghijklmnop",
            "/cli-login/?port=8123&state=short",
            "/cli-login/?port=8123&state=abcdefghijklmnop%22",
        ]:
            with self.subTest(url=invalid):
                self.assertEqual(self.client.get(invalid).status_code, 400)

        response = self.client.post(url)
        token = user.api_tokens.get()
        self.assertEqual(token.title, "wb (laptop)")
        self.assertContains(response, 'action="http://127.0.0.1:8123/"')
        self.assertContains(response, 'value="abcdefghijklmnop"')
        secret = (
            response.content.decode().split('name="token" value="')[1].split('"')[0]
        )
        self.assertEqual(APIToken.objects.user_for(secret), user)

    def test_language(self):
        """Token authenticated requests use the user's language"""
        user = factories.UserFactory.create(language="en")
        _token, secret = APIToken.create_for(user=user, title="CLI")
        response = self.client.post(
            "/api/projects/",
            {"title": "X", "customer": 0},
            content_type="application/json",
            headers={"authorization": f"Bearer {secret}", "accept-language": "de"},
        )
        self.assertEqual(
            response.json()["detail"][0]["msg"],
            "Select a valid choice. That choice is not one of the available choices.",
        )

    def test_audit_user(self):
        """Changes through the API are logged with the token's user"""
        project = factories.ProjectFactory.create()
        _token, secret = APIToken.create_for(user=project.owned_by, title="CLI")

        response = self.client.patch(
            f"/api/projects/{project.pk}/",
            {"title": "Changed"},
            content_type="application/json",
            headers={"authorization": f"Bearer {secret}"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        # Changes of a test happen in the same transaction
        action = (
            LoggedAction.objects
            .for_model(project)
            .with_data(id=project.id)
            .latest("event_id")
        )
        self.assertEqual(action.user_id, project.owned_by.id, action.user_name)
