from django.test import TestCase

from workbench import factories
from workbench.audit.models import LoggedAction


class AuditTest(TestCase):
    def test_admin(self):
        """The audit trail cannot be changed through the Django admin"""
        # Generate some objects
        factories.ProjectFactory.create()

        user = factories.UserFactory.create(is_admin=True)
        self.client.force_login(user)

        user.planning_hours_per_day = 1
        user.save()

        response = self.client.get("/admin/audit/loggedaction/")
        self.assertNotContains(response, "add/")
        self.assertNotContains(response, "<select")
        self.assertContains(response, "INSERT")
        self.assertContains(response, "UPDATE")  # change

        response = self.client.get(
            "/admin/audit/loggedaction/{}/change/".format(
                LoggedAction.objects.all()[0].pk
            )
        )
        self.assertNotContains(response, 'type="text"')
        self.assertNotContains(response, "<select")
        self.assertNotContains(response, "<textarea")
        # print(response, response.content.decode("utf-8"))
