from django.test import TestCase

from workbench import factories
from workbench.audit.models import LoggedAction


class AuditTest(TestCase):
    def test_admin(self):
        # Generate some objects
        factories.ProjectFactory.create()

        user = factories.UserFactory.create(is_admin=True)
        self.client.force_login(user)

        response = self.client.get("/admin/audit/loggedaction/")
        self.assertNotContains(response, "add/")
        self.assertNotContains(response, "<select")
        self.assertContains(response, "UPDATE accounts_user")  # login
        self.assertContains(response, "INSERT accounts_user")

        response = self.client.get(
            "/admin/audit/loggedaction/{}/change/".format(
                LoggedAction.objects.all()[0].pk
            )
        )
        self.assertNotContains(response, 'type="text"')
        self.assertNotContains(response, "<select")
        self.assertNotContains(response, "<textarea")
        # print(response, response.content.decode("utf-8"))
