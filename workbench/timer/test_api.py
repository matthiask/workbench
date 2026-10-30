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
        data = create(type="stop", minutes=-5, notes="Wireframes").json()
        self.assertEqual(data["created_at"], "2026-10-30T11:55:00+01:00")
        self.assertEqual(data["notes"], "Wireframes")
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

        data = self.client.get("/api/timestamps/?day=2026-10-29").json()
        self.assertEqual(data["slices"], [])
