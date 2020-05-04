import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from freezegun import freeze_time

from workbench import factories
from workbench.accounts.models import User
from workbench.timer.models import Timestamp


class TimerTest(TestCase):
    def test_timer(self):
        user = factories.UserFactory.create(is_admin=True)
        self.client.force_login(user)

        response = self.client.get("/timer/")
        self.assertContains(response, "data-current-user")


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
        self.assertIn("Start @", str(t))

        response = self.client.post(t.get_delete_url())
        self.assertRedirects(response, "/timestamps/")

    def test_timestamp_auth(self):
        response = self.client.post("/create-timestamp/", {"type": "bla"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/create-timestamp/", {"type": "start"})
        self.assertEqual(response.status_code, 400)

        user = factories.UserFactory.create()

        response = self.client.post(
            "/create-timestamp/", {"type": "start", "user": user.email}
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/create-timestamp/", {"type": "start", "user": user.signed_email}
        )
        self.assertEqual(response.status_code, 201)

        t = Timestamp.objects.get()
        self.assertEqual(t.user, user)

    def test_timestamp_with_time(self):
        user = factories.UserFactory.create()

        response = self.client.post(
            "/create-timestamp/",
            {"type": "start", "user": user.signed_email, "time": "09:23"},
        )
        self.assertEqual(response.status_code, 201)

        t = Timestamp.objects.get()
        created_at = timezone.localtime(t.created_at)
        self.assertEqual(created_at.hour, 9)
        self.assertEqual(created_at.minute, 23)

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

        timestamps = Timestamp.objects.for_user(user)["timestamps"]
        self.assertEqual(
            timestamps,
            [
                {"elapsed": None, "previous": None, "timestamp": t1},
                {"elapsed": Decimal("0.7"), "previous": t1, "timestamp": t2},
                {"elapsed": Decimal("0.4"), "previous": t2, "timestamp": t3},
                {"elapsed": Decimal("1.0"), "previous": t3, "timestamp": t4},
                # 0.0 after a STOP
                {"elapsed": None, "previous": t4, "timestamp": t5},
                {"elapsed": Decimal("0.4"), "previous": t5, "timestamp": t6},
            ],
        )

        # Some types have been overridden
        self.assertEqual(
            [row["timestamp"].type for row in timestamps],
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
            type=Timestamp.START, created_at=today + dt.timedelta(minutes=29)
        )

        timestamps = Timestamp.objects.for_user(user)["timestamps"]
        self.assertEqual(
            timestamps,
            [
                {"elapsed": None, "previous": None, "timestamp": t1},
                {"elapsed": Decimal("0.5"), "previous": t1, "timestamp": t2},
            ],
        )
        self.assertEqual(
            [row["timestamp"].type for row in timestamps],
            [Timestamp.START, Timestamp.SPLIT],  # 2nd was: START
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

        timestamps = Timestamp.objects.for_user(user)["timestamps"]
        self.assertEqual(
            timestamps,
            [
                {"elapsed": None, "previous": None, "timestamp": t1},
                {"elapsed": Decimal("0.5"), "previous": t1, "timestamp": t2},
            ],
        )
        self.assertEqual(
            [row["timestamp"].type for row in timestamps],
            [Timestamp.START, Timestamp.STOP],
        )

    def test_latest_logbook_entry(self):
        today = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        user = factories.UserFactory.create()

        self.assertEqual(Timestamp.objects.for_user(user)["timestamps"], [])

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

        timestamps = Timestamp.objects.for_user(user)["timestamps"]
        self.assertEqual(len(timestamps), 3)
        self.assertEqual(timestamps[0]["elapsed"], None)
        self.assertEqual(timestamps[1]["elapsed"], None)
        self.assertEqual(timestamps[2]["elapsed"], Decimal("0.2"))

        self.assertEqual(timestamps[0]["timestamp"], t1)
        self.assertIn(l1.description, timestamps[1]["timestamp"].pretty_notes)
        self.assertEqual(timestamps[2]["timestamp"], t2)

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

    def test_latest_created_at(self):
        user = factories.UserFactory.create()
        self.assertEqual(user.latest_created_at, None)

        t = user.timestamp_set.create(
            created_at=timezone.now() - dt.timedelta(seconds=99), type=Timestamp.SPLIT
        )
        user = User.objects.get(id=user.id)
        self.assertEqual(user.latest_created_at, t.created_at)

        h = factories.LoggedHoursFactory.create(rendered_by=user)
        user = User.objects.get(id=user.id)
        self.assertEqual(user.latest_created_at, h.created_at)

        t = user.timestamp_set.create(
            created_at=timezone.now() + dt.timedelta(seconds=99), type=Timestamp.SPLIT
        )
        user = User.objects.get(id=user.id)
        self.assertEqual(user.latest_created_at, t.created_at)

        h = factories.LoggedHoursFactory.create(
            rendered_by=user, created_at=timezone.now() + dt.timedelta(seconds=300)
        )
        user = User.objects.get(id=user.id)
        self.assertEqual(user.latest_created_at, h.created_at)

        # After assigning the logged_hours relation latest_created_at should
        # be back to Timestamp.created_at
        t.logged_hours = h
        t.save()

        user = User.objects.get(id=user.id)
        self.assertEqual(user.latest_created_at, t.created_at)

    def test_link_timestamps(self):
        service = factories.ServiceFactory.create()
        user = service.project.owned_by
        self.client.force_login(user)

        t = user.timestamp_set.create(
            created_at=timezone.now() - dt.timedelta(seconds=99), type=Timestamp.SPLIT
        )

        response = self.client.post(
            service.project.urls["createhours"] + "?timestamp={}".format(t.pk),
            {
                "modal-rendered_by": user.pk,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-service": service.id,
                "modal-hours": "0.2",
                "modal-description": "Test",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        t.refresh_from_db()
        self.assertEqual(t.logged_hours.description, "Test")

    def test_autodetect_possible_break(self):
        today = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        user = factories.UserFactory.create()

        l1 = factories.LoggedHoursFactory.create(
            rendered_by=user,
            created_at=today + dt.timedelta(minutes=0),
            description="ABC",
            hours=1,
        )

        l2 = factories.LoggedHoursFactory.create(
            rendered_by=user,
            created_at=today + dt.timedelta(minutes=90),
            description="ABC",
            hours=1,
        )

        l3 = factories.LoggedHoursFactory.create(
            rendered_by=user,
            created_at=today + dt.timedelta(minutes=155),
            description="ABC",
            hours=1,
        )

        for_user = Timestamp.objects.for_user(user)
        self.assertEqual(for_user["hours"], Decimal("3"))
        timestamps = for_user["timestamps"]

        self.assertEqual(len(timestamps), 4)
        self.assertEqual(timestamps[0]["timestamp"].logged_hours, l1)
        self.assertEqual(timestamps[2]["timestamp"].logged_hours, l2)
        self.assertEqual(timestamps[3]["timestamp"].logged_hours, l3)

        auto = timestamps[1]
        self.assertEqual(auto["elapsed"], Decimal("0.5"))
        self.assertEqual(
            auto["timestamp"].comment, "Maybe the start of the next logbook entry?"
        )

    def test_list_timestamps(self):
        user = factories.UserFactory.create()

        response = self.client.get("/list-timestamps/")
        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            "/list-timestamps/?user={}".format(user.signed_email)
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data, {"hours": "0", "user": str(user), "success": True, "timestamps": []}
        )

        user.timestamp_set.create(
            type=Timestamp.START, created_at=timezone.now() - dt.timedelta(seconds=10)
        )
        user.timestamp_set.create(type=Timestamp.SPLIT)

        response = self.client.get(
            "/list-timestamps/?user={}".format(user.signed_email)
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["timestamps"]), 2)
        self.assertEqual(data["timestamps"][1]["elapsed"], "0.1")

    def test_pretty(self):
        hours = factories.LoggedHoursFactory.create()
        brk = factories.BreakFactory.create()

        self.assertEqual(Timestamp(logged_hours=hours).pretty_type, "logbook")
        self.assertEqual(Timestamp(logged_break=brk).pretty_type, "break")

        self.assertEqual(Timestamp(logged_break=brk).pretty_notes, str(brk))
