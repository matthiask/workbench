import datetime as dt
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime
from django.utils.translation import deactivate_all

from freezegun import freeze_time

from workbench import factories
from workbench.accounts.models import User
from workbench.timer.models import Timestamp
from workbench.tools.formats import local_date_format


class TimerTest(TestCase):
    def test_timer(self):
        """The timer view does not crash"""
        user = factories.UserFactory.create(is_admin=True)
        self.client.force_login(user)

        response = self.client.get("/timer/")
        self.assertContains(response, "data-current-user")


class TimestampsTest(TestCase):
    @freeze_time("2020-02-20T03:00:00+00:00")
    def test_timestamp(self):
        """Basic smoke test of timestamp creation and deletion"""
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
        self.assertEqual(str(t), "blub")

        response = self.client.post(reverse("delete_timestamp", args=(t.pk,)))
        self.assertRedirects(response, "/timestamps/")

    def test_timestamp_auth(self):
        """The API supports different authorizations"""
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
        """Specifying a time makes the endpoint use it instead of the current time"""
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
        """Test a scenario with a break in the middle"""
        today = localtime(timezone.now()).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        user = factories.UserFactory.create()

        # Insert STOPs at the beginning -- they should be skipped
        ts1 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today - dt.timedelta(minutes=60)
        )
        ts2 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today - dt.timedelta(minutes=80)
        )

        t1 = user.timestamp_set.create(
            type=Timestamp.START, created_at=today, notes="Aaa",
        )
        # t2 =  # unused
        user.timestamp_set.create(
            type=Timestamp.STOP,
            created_at=today + dt.timedelta(minutes=40),
            notes="Bbb",
        )
        t3 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=60)
        )
        t4 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=115)
        )
        t5 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=140)
        )
        t6 = user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=160)
        )

        slices = Timestamp.objects.slices(user)

        partial = [
            (
                slice.elapsed_hours,
                local_date_format(slice.get("starts_at"), fmt="H:i"),
                local_date_format(slice.get("ends_at"), fmt="H:i"),
                slice.get("timestamp_id"),
                slice["description"],
                slice.get("comment"),
            )
            for slice in slices
        ]

        self.assertEqual(
            partial,
            [
                (None, "", "07:40", ts2.pk, "", None),
                (Decimal("0.4"), "07:40", "08:00", ts1.pk, "", None),
                (Decimal("1.0"), "08:00", "09:00", None, "", "<detected>"),
                (Decimal("0.7"), "09:00", "09:40", t1.pk, "Aaa; Bbb", None),
                (Decimal("0.4"), "09:40", "10:00", t3.pk, "", None),
                (Decimal("1.0"), "10:00", "10:55", t4.pk, "", None),
                (Decimal("0.5"), "10:55", "11:20", t5.pk, "", None),
                (Decimal("0.4"), "11:20", "11:40", t6.pk, "", None),
            ],
        )

    def test_latest_logbook_entry(self):
        """Timestamps are automatically created for logged hours"""
        today = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        user = factories.UserFactory.create()

        self.assertEqual(Timestamp.objects.slices(user), [])

        user.timestamp_set.create(
            type=Timestamp.START, created_at=today + dt.timedelta(minutes=0)
        )
        l1 = factories.LoggedHoursFactory.create(
            rendered_by=user,
            created_at=today + dt.timedelta(minutes=10),
            description="ABC",
            hours=Decimal("0.2"),  # It was only ten minutes
        )
        user.timestamp_set.create(
            type=Timestamp.STOP, created_at=today + dt.timedelta(minutes=20)
        )

        slices = Timestamp.objects.slices(user)
        self.assertEqual(len(slices), 3)
        self.assertEqual(slices[0].elapsed_hours, Decimal("0.2"))
        self.assertEqual(slices[1].elapsed_hours, Decimal("0.2"))
        self.assertEqual(slices[2].elapsed_hours, Decimal("0.2"))

        self.assertTrue(slices[0].show_create_buttons)
        self.assertFalse(slices[1].show_create_buttons)
        self.assertTrue(slices[2].show_create_buttons)

        self.assertEqual(l1, slices[1]["description"])

    def test_view(self):
        """The timestamps view does not crash"""
        deactivate_all()
        user = factories.UserFactory.create()
        user.timestamp_set.create(type=Timestamp.START)

        self.client.force_login(user)
        response = self.client.get("/timestamps/")
        self.assertContains(response, "timestamps")

    def test_controller(self):
        """The timestamps controller does not crash"""
        response = self.client.get("/timestamps-controller/")
        self.assertContains(response, "Timestamps")

    def test_latest_created_at(self):
        """User.latest_created_at takes logged hours AND timestamps into account"""
        user = factories.UserFactory.create()
        self.assertEqual(user.latest_created_at, None)

        t = user.timestamp_set.create(
            created_at=timezone.now() - dt.timedelta(seconds=99), type=Timestamp.STOP
        )
        user = User.objects.get(id=user.id)
        self.assertEqual(user.latest_created_at, t.created_at)

        h = factories.LoggedHoursFactory.create(rendered_by=user)
        user = User.objects.get(id=user.id)
        self.assertEqual(user.latest_created_at, h.created_at)

        t = user.timestamp_set.create(
            created_at=timezone.now() + dt.timedelta(seconds=99), type=Timestamp.STOP
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
        """Linking logged hours to timestamps"""
        service = factories.ServiceFactory.create()
        user = service.project.owned_by
        self.client.force_login(user)

        t = user.timestamp_set.create(
            created_at=timezone.now() - dt.timedelta(seconds=99), type=Timestamp.STOP
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

    def test_list_timestamps(self):
        """The timestamps listing endpoint works"""
        user = factories.UserFactory.create()

        response = self.client.get("/list-timestamps/")
        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            "/list-timestamps/?user={}".format(user.signed_email)
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data, {"hours": "0.0", "user": str(user), "success": True, "timestamps": []}
        )

        user.timestamp_set.create(
            type=Timestamp.START, created_at=timezone.now() - dt.timedelta(seconds=10)
        )
        user.timestamp_set.create(type=Timestamp.STOP)

        response = self.client.get(
            "/list-timestamps/?user={}".format(user.signed_email)
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["timestamps"]), 2)
        self.assertEqual(data["timestamps"][0]["elapsed"], "0.1")
        self.assertEqual(data["timestamps"][1]["elapsed"], None)

    def test_post_split(self):
        """Backwards compatibility: Type "split" still works"""
        self.client.force_login(factories.UserFactory.create())

        response = self.client.post("/create-timestamp/", {"type": "split"})
        self.assertEqual(response.status_code, 201)

        t = Timestamp.objects.get()
        self.assertEqual(t.type, "stop")

    def test_gap_between_hours_and_start(self):
        """A slice is automatically generated if there is a gap between a
        log/stop and a start"""
        hours = factories.LoggedHoursFactory.create(
            created_at=timezone.now() - dt.timedelta(minutes=33),
        )
        user = hours.rendered_by
        user.timestamp_set.create(type=Timestamp.START, notes="Mittag")

        slices = Timestamp.objects.slices(user)
        self.assertEqual(len(slices), 3)
        self.assertEqual(slices[1]["comment"], "<detected>")

    def test_gap_between_logbook_entries(self):
        """A slice is automatically generated if the gap between subsequent
        logbook entries if there is a gap in-between"""
        user = factories.UserFactory.create()

        factories.LoggedHoursFactory.create(
            rendered_by=user, created_at=timezone.now() - dt.timedelta(seconds=10799)
        )
        factories.LoggedHoursFactory.create(rendered_by=user)

        slices = Timestamp.objects.slices(user)
        self.assertEqual(len(slices), 3)
        self.assertEqual(slices[1].elapsed_hours, Decimal("2"))
