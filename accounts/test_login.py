from django.test import TestCase

from ftool import factories


class LoginTestCase(TestCase):
    def test_login(self):
        user = factories.UserFactory.create()

        self.assertRedirects(
            self.client.get('/'),
            '/accounts/login/')

        self.client.login(email=user.email)

        self.assertContains(
            self.client.get('/'),
            'href="/accounts/logout/"',
            1,
            status_code=200)
