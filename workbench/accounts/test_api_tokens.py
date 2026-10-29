from django.test import Client, TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.models import APIToken


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

        # The reporting API uses its own token
        self.assertEqual(
            self.client.get(
                "/api/key-data/", headers={"authorization": f"Bearer {secret}"}
            ).status_code,
            401,
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
