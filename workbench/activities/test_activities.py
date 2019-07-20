from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from workbench import factories
from workbench.tools.testing import messages


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

        response = self.client.post(
            activity.urls["update"],
            {
                "title": activity.title,
                "notes": activity.notes,
                "owned_by": activity.owned_by_id,
                "due_on": "",
                "is_completed": "on",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        activity.refresh_from_db()
        self.assertEqual(activity.completed_at.date(), date.today())

        response = self.client.get(activity.urls["list"])
        self.assertContains(response, "1 &ndash; 20 von 20")

        response = self.client.get(activity.urls["list"] + "?s=all")
        self.assertContains(response, "1 &ndash; 21 von 21")

        response = self.client.get(activity.urls["list"] + "?owned_by=0")
        self.assertContains(response, "0 &ndash; 0 von 0")

        response = self.client.get(
            activity.urls["list"] + "?owned_by={}".format(activity.owned_by_id)
        )
        self.assertContains(response, "1 &ndash; 20 von 20")

        response = self.client.get(
            activity.urls["list"] + "?owned_by={}".format(activity.owned_by_id + 1)
        )
        self.assertEqual(messages(response), ["Suchformular war ungültig."])

    def test_activity_creation(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(factories.UserFactory.create())

        url = "/activities/create/?project={}".format(project.pk)
        response = self.client.post(
            url,
            {
                "title": "Call back",
                "notes": "",
                "owned_by": project.owned_by_id,
                "due_on": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)
        activity = factories.Activity.objects.get()
        self.assertIsNone(activity.contact)
        self.assertIsNone(activity.deal)
        self.assertEqual(activity.project, project)
        self.assertEqual(activity.owned_by, project.owned_by)

        response = self.client.get("/activities/")
        self.assertContains(
            response, "Aktivität &#39;Call back&#39; wurde erfolgreich erstellt."
        )

        response = self.client.get("/activities/?project=" + str(project.pk + 1))
        self.assertRedirects(response, "/activities/?e=1")
        response = self.client.get("/activities/?project=" + str(project.pk))
        self.assertContains(response, activity.title)

        url = "/activities/create/?deal=234"  # Deal does not exist.
        response = self.client.post(
            url,
            {
                "title": "Stuff",
                "notes": "",
                "owned_by": project.owned_by_id,
                "due_on": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        activity = factories.Activity.objects.latest("pk")
        self.assertIsNone(activity.deal)
        self.assertEqual(activity.title, "Stuff")

    def test_activity_uncomplete(self):
        activity = factories.ActivityFactory.create(completed_at=timezone.now())
        self.client.force_login(activity.owned_by)
        response = self.client.post(
            activity.urls["update"],
            {
                "title": "Stuff",
                "notes": "",
                "owned_by": activity.owned_by_id,
                "due_on": "",
                "is_completed": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)
        activity.refresh_from_db()
        self.assertIsNone(activity.completed_at)

    def test_non_ajax_redirect(self):
        activity = factories.ActivityFactory.create()
        self.client.force_login(activity.owned_by)
        response = self.client.get(activity.urls["detail"])
        self.assertRedirects(response, activity.urls["list"])
