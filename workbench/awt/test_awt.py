from django.test import TestCase

from workbench import factories
from workbench.awt.models import Year


class AWTTest(TestCase):
    def test_redirect(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get("/report/annual-working-time/")
        self.assertRedirects(response, "/")

        factories.YearFactory.create()
        response = self.client.get("/report/annual-working-time/")
        self.assertEqual(response.status_code, 200)

    def test_absences_list(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get("/absences/")
        self.assertRedirects(response, "/absences/?u={}".format(user.pk))
