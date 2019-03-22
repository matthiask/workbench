from datetime import date, timedelta

from django.test import TestCase

from workbench import factories


class ActivitiesTest(TestCase):
    def test_activities(self):
        activity = factories.ActivityFactory.create()
        for i in range(-1, 19):
            factories.ActivityFactory.create(
                owned_by=activity.owned_by, due_on=date.today() + timedelta(days=i)
            )

        self.client.force_login(activity.owned_by)
        response = self.client.get("/")

        response = self.client.get(activity.urls["list"])
        self.assertContains(response, "überfällig")
        self.assertContains(response, "heute fällig")
        self.assertContains(response, "morgen fällig")
        self.assertContains(response, "fällig in 2 Tagen")
        self.assertContains(response, "fällig in 14 Tagen")
        self.assertContains(response, "fällig in 2 Wochen")
        self.assertContains(response, "1 &ndash; 21 von 21")

        self.client.post(
            activity.urls["update"],
            {
                "title": activity.title,
                "notes": activity.notes,
                "owned_by": activity.owned_by_id,
                "due_on": "",
                "is_completed": "on",
            },
        )

        activity.refresh_from_db()
        self.assertEqual(activity.completed_at.date(), date.today())

        response = self.client.get(activity.urls["list"])
        self.assertContains(response, "1 &ndash; 20 von 20")
        self.assertContains(response, "21 insgesamt")
