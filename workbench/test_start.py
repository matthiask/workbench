from django.test import TestCase

from workbench import factories
from workbench.tools.validation import monday
from workbench.views import OTHERS_HOURS_SHOWN


class StartTest(TestCase):
    def test_no_active_projects(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get("/")
        self.assertContains(response, "No active projects")

    def test_others_hours(self):
        """The others' hours, the user's own are listed separately"""
        user = factories.UserFactory.create()
        other = factories.UserFactory.create()
        own = factories.LoggedHoursFactory.create(
            rendered_by=user, description="My own work"
        )
        for i in range(OTHERS_HOURS_SHOWN + 2):
            factories.LoggedHoursFactory.create(
                rendered_by=other,
                service=own.service,
                description=f"Their work {i}",
            )
        self.client.force_login(user)

        response = self.client.get("/")
        self.assertContains(response, "My own work", count=1)
        self.assertContains(response, "wb-feed-row", count=OTHERS_HOURS_SHOWN + 2)
        self.assertContains(response, "Show 2 more")

    def test_hours_rings_link(self):
        """The rings show today's and this week's hours, their link this week's"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get("/")
        self.assertContains(
            response, f"?rendered_by={user.pk}&amp;date_from={monday().isoformat()}"
        )
