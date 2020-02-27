import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from freezegun import freeze_time

from workbench import factories
from workbench.timer.models import TimerState, Timestamp


class TimerTest(TestCase):
    def test_timer(self):
        user = factories.UserFactory.create(is_admin=True)
        self.client.force_login(user)

        response = self.client.get("/timer/")
        self.assertContains(response, 'id="timer-state"')

        response = self.client.post("/timer/", data={"state": "[blub"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/timer/", data={"state": '{"a": 1}'})
        self.assertEqual(response.status_code, 200)

        state = TimerState.objects.get()
        self.assertEqual(state.state, {"a": 1})
        self.assertEqual(str(state), str(user))

        response = self.client.get(
            "/admin/timer/timerstate/{}/change/".format(state.id)
        )
        self.assertContains(
            response,
            '<div class="readonly"><code><pre>{&#x27;a&#x27;: 1}</pre></code></div>',
        )


class TimestampsTest(TestCase):
    @freeze_time("2020-02-20T03:00:00+00:00")
    def test_timestamp(self):
        self.client.force_login(factories.UserFactory.create())

        response = self.client.post("/create-timestamp/", {"type": "bla"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/create-timestamp/", {"type": "start", "notes": "blub"}
        )
        self.assertEqual(response.status_code, 201)

        t = Timestamp.objects.get()
        self.assertEqual(t.type, "start")
        self.assertEqual(t.notes, "blub")
        self.assertIn(str(t), {"20.02.2020 04:00", "20.02.2020 05:00"})

    def test_timestamp_auth(self):
        response = self.client.post("/create-timestamp/", {"type": "bla"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/create-timestamp/", {"type": "start"})
        self.assertEqual(response.status_code, 403)

        user = factories.UserFactory.create()

        response = self.client.post(
            "/create-timestamp/", {"type": "start", "user": user.email}
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/create-timestamp/", {"type": "start", "user": user.signed_email}
        )
        self.assertEqual(response.status_code, 201)

        t = Timestamp.objects.get()
        self.assertEqual(t.user, user)

    def test_timestamps_scenario(self):
        today = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        user = factories.UserFactory.create()

        # Insert STOPs at the beginning -- they should be skipped
        user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today - dt.timedelta(minutes=60)
        )
        user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today - dt.timedelta(minutes=80)
        )

        t1 = user.timestamp_set.create(type=Timestamp.START, created_at=today)
        t2 = user.timestamp_set.create(
            type=Timestamp.SPLIT, created_at=today + dt.timedelta(minutes=40)
        )
        t3 = user.timestamp_set.create(
            type=Timestamp.SPLIT, created_at=today + dt.timedelta(minutes=60)
        )
        t4 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=115)
        )
        t5 = user.timestamp_set.create(
            type=Timestamp.SPLIT, created_at=today + dt.timedelta(minutes=140)
        )
        t6 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=160)
        )

        self.assertEqual(
            user.timestamps,
            [
                {"elapsed": None, "timestamp": t1},
                {"elapsed": Decimal("0.7"), "timestamp": t2},
                {"elapsed": Decimal("0.4"), "timestamp": t3},
                {"elapsed": Decimal("1.0"), "timestamp": t4},
                # 0.0 after a STOP
                {"elapsed": None, "timestamp": t5},
                {"elapsed": Decimal("0.4"), "timestamp": t6},
            ],
        )

        # Some types have been overridden
        self.assertEqual(
            [row["timestamp"].type for row in user.timestamps],
            [
                Timestamp.START,
                Timestamp.SPLIT,
                Timestamp.SPLIT,
                Timestamp.STOP,
                Timestamp.START,  # Was: SPLIT
                Timestamp.STOP,
            ],
        )

    def test_timestamps_start_start(self):
        today = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        user = factories.UserFactory.create()

        t1 = user.timestamp_set.create(
            type=Timestamp.START, created_at=today + dt.timedelta(minutes=0)
        )
        t2 = user.timestamp_set.create(
            type=Timestamp.START, created_at=today + dt.timedelta(minutes=30)
        )

        self.assertEqual(
            user.timestamps[:2],  # Cut off the auto-now timestamp
            [{"elapsed": None, "timestamp": t1}, {"elapsed": None, "timestamp": t2}],
        )
        self.assertEqual(
            [row["timestamp"].type for row in user.timestamps],
            [Timestamp.START, Timestamp.START, Timestamp.SPLIT],
        )

    def test_timestamps_stop_stop(self):
        """Test that repeated STOPs are dropped"""
        today = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        user = factories.UserFactory.create()

        t1 = user.timestamp_set.create(
            type=Timestamp.START, created_at=today + dt.timedelta(minutes=0)
        )
        t2 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=30)
        )
        user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=40)
        )

        self.assertEqual(
            user.timestamps,
            [
                {"elapsed": None, "timestamp": t1},
                {"elapsed": Decimal("0.5"), "timestamp": t2},
            ],
        )
        self.assertEqual(
            [row["timestamp"].type for row in user.timestamps],
            [Timestamp.START, Timestamp.STOP],
        )

    def test_latest_logbook_entry(self):
        today = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        user = factories.UserFactory.create()

        self.assertEqual(Timestamp.for_user(user), [])

        t1 = user.timestamp_set.create(
            type=Timestamp.START, created_at=today + dt.timedelta(minutes=0)
        )
        l1 = factories.LoggedHoursFactory.create(
            rendered_by=user,
            created_at=today + dt.timedelta(minutes=10),
            description="ABC",
        )
        t2 = user.timestamp_set.create(
            type=Timestamp.SPLIT, created_at=today + dt.timedelta(minutes=20)
        )

        self.assertEqual(len(user.timestamps), 4)  # Three timestamps plus auto-now
        self.assertEqual(user.timestamps[0]["elapsed"], None)
        self.assertEqual(user.timestamps[1]["elapsed"], None)
        self.assertEqual(user.timestamps[2]["elapsed"], Decimal("0.2"))

        self.assertEqual(user.timestamps[0]["timestamp"], t1)
        self.assertIn(l1.description, user.timestamps[1]["timestamp"].notes)
        self.assertEqual(user.timestamps[2]["timestamp"], t2)

    def test_view(self):
        deactivate_all()
        user = factories.UserFactory.create()
        user.timestamp_set.create(type=Timestamp.START)

        self.client.force_login(user)
        response = self.client.get("/timestamps/")
        self.assertContains(response, "timestamps")

    def test_controller(self):
        response = self.client.get("/timestamps-controller/")
        self.assertContains(response, "Timestamps")
