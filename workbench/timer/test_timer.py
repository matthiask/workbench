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

        response = self.client.post(
            "/create-timestamp/", {"type": "start", "user": "test"}
        )
        self.assertEqual(response.status_code, 403)

        user = factories.UserFactory.create()
        response = self.client.post(
            "/create-timestamp/", {"type": "start", "user": user.signed_email}
        )
        self.assertEqual(response.status_code, 201)

        t = Timestamp.objects.get()
        self.assertEqual(t.user, user)

    def test_structured(self):
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

        self.assertEqual(
            user.timestamps,
            [
                {"elapsed": Decimal("0.0"), "timestamp": t1},
                {"elapsed": Decimal("0.7"), "timestamp": t2},
                {"elapsed": Decimal("0.4"), "timestamp": t3},
                {"elapsed": Decimal("1.0"), "timestamp": t4},
                # 0.0 after a STOP
                {"elapsed": Decimal("0.0"), "timestamp": t5},
            ],
        )

        # Type has been overridden
        self.assertEqual(user.timestamps[-1]["timestamp"].type, Timestamp.START)

    def test_view(self):
        deactivate_all()
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/timestamps/")
        self.assertContains(response, "timestamps")
