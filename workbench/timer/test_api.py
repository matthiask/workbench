from django.test import TestCase
from django.utils.translation import deactivate_all
from time_machine import travel

from workbench import factories
from workbench.timer.models import Timestamp


class TimestampsAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    @travel("2026-10-30T12:00:00+01:00", tick=False)
    def test_create(self):
        """Timestamps are created now, at a time or relative to now"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def create(**data):
            return self.client.post(
                "/api/timestamps/", data, content_type="application/json"
            )

        data = create(type="start").json()
        self.assertEqual(data["created_at"], "2026-10-30T12:00:00+01:00")
        self.assertIsNone(data["slice"]["ends_at"])
        data = create(type="stop", minutes=30, notes="Wireframes").json()
        self.assertEqual(data["created_at"], "2026-10-30T12:30:00+01:00")
        self.assertEqual(data["notes"], "Wireframes")
        # The stopped task
        self.assertEqual(data["slice"]["starts_at"], "2026-10-30T12:00:00+01:00")
        self.assertEqual(data["slice"]["hours"], "0.5")
        data = create(type="stop", time="13:30").json()
        self.assertEqual(data["created_at"], "2026-10-30T13:30:00+01:00")
        self.assertEqual(Timestamp.objects.filter(user=user).count(), 3)

        self.assertEqual(create(type="split").status_code, 422)
        self.assertEqual(create(type="stop", time="13:30", minutes=5).status_code, 422)

    @travel("2026-10-30T12:00:00+01:00", tick=False)
    def test_list(self):
        """The day's slices, unlogged ones link to the logbook form"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        Timestamp.objects.create(user=user, type=Timestamp.START)
        Timestamp.objects.create(user=user, type=Timestamp.STOP, notes="Wireframes")
        hours = factories.LoggedHoursFactory.create(rendered_by=user, hours=2)

        data = self.client.get("/api/timestamps/").json()
        self.assertEqual(data["day"], "2026-10-30")
        self.assertEqual(data["logged_hours"], "2.0")
        [unlogged] = [s for s in data["slices"] if not s["is_logged"]]
        self.assertEqual(unlogged["description"], "Wireframes")
        self.assertIn("/logbook/hours/create/", unlogged["log_hours_url"])
        [logged] = [s for s in data["slices"] if s["is_logged"]]
        self.assertEqual(logged["project"]["id"], hours.service.project_id)
        self.assertIsNone(logged["log_hours_url"])

        self.assertEqual(data["weekly_hours"], "2.0")
        self.assertEqual(data["running_hours"], "0.1")

        data = self.client.get("/api/timestamps/?day=2026-10-29").json()
        self.assertEqual(data["slices"], [])
        self.assertEqual(data["weekly_hours"], "2.0")
        self.assertIsNone(data["running_since"])

    def test_delete(self):
        """Timestamps can be deleted, the latest of today undone"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        first = Timestamp.objects.create(user=user, type=Timestamp.START)
        latest = Timestamp.objects.create(user=user, type=Timestamp.STOP)
        other = Timestamp.objects.create(
            user=factories.UserFactory.create(), type=Timestamp.STOP
        )

        response = self.client.delete("/api/timestamps/latest/")
        self.assertEqual(response.json()["id"], latest.pk)
        response = self.client.delete(f"/api/timestamps/{other.pk}/")
        self.assertEqual(response.status_code, 404)
        response = self.client.delete(f"/api/timestamps/{first.pk}/")
        self.assertEqual(response.json()["id"], first.pk)
        response = self.client.delete("/api/timestamps/latest/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(list(Timestamp.objects.all()), [other])
