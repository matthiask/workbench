import datetime as dt

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from freezegun import freeze_time

from workbench import factories
from workbench.logbook.models import Break
from workbench.timer.models import Timestamp
from workbench.tools.testing import check_code


class BreaksTest(TestCase):
    def test_list(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        Break.objects.create(
            user=factories.UserFactory.create(),
            day=dt.date.today(),
            starts_at=dt.time(12, 0),
            ends_at=dt.time(13, 0),
        )

        code = check_code(self, "/logbook/breaks/")
        code("")
        code("user=-1")
        code("user={}".format(user.pk))

    def test_valid_break(self):
        brk = Break(
            user=factories.UserFactory.create(),
            day=dt.date.today(),
            starts_at=dt.time(12, 0),
            ends_at=dt.time(13, 0),
        )
        brk.full_clean()
        self.assertEqual(brk.timedelta.total_seconds(), 3600)

    def test_break_validation(self):
        with self.assertRaises(ValidationError) as cm:
            Break(
                user=factories.UserFactory.create(),
                day=dt.date.today(),
                starts_at=dt.time(12, 0),
                ends_at=dt.time(11, 0),
            ).full_clean()

        self.assertEqual(
            list(cm.exception),
            [("ends_at", ["Breaks should end later than they begin."])],
        )

    @freeze_time("2020-01-02")
    def test_break_form_initial(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get(Break.urls["create"])
        self.assertContains(response, 'value="2020-01-02"')

        response = self.client.get(Break.urls["create"] + "?day=2020-01-01")
        self.assertContains(response, 'value="2020-01-01"')
        self.assertNotContains(response, 'value="2020-01-02"')

        response = self.client.get(Break.urls["create"] + "?starts_at=09:00:00")
        self.assertContains(response, 'value="09:00:00"')

        user.timestamp_set.create(
            created_at=timezone.now() - dt.timedelta(days=1), type=Timestamp.SPLIT
        )

        response = self.client.get(Break.urls["create"])
        self.assertContains(response, 'value="2020-01-02"')
        self.assertNotContains(response, 'value="2020-01-01"')

    def test_break_from_timestamps(self):
        user = factories.UserFactory.create()
        now = timezone.localtime(timezone.now()).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        user.timestamp_set.create(type=Timestamp.SPLIT, created_at=now)
        user.timestamp_set.create(
            type=Timestamp.SPLIT, created_at=now - dt.timedelta(seconds=900)
        )

        self.client.force_login(user)

        response = self.client.get("/timestamps/")
        self.assertContains(response, "starts_at=08:45:00")
        self.assertContains(response, "ends_at=09:00:00")

    def test_break_form_save_creates_timestamp(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.post(
            Break.urls["create"],
            {
                "day": dt.date.today().isoformat(),
                "starts_at": "12:00",
                "ends_at": "12:45",
                "description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        brk = user.breaks.get()
        t = user.timestamp_set.latest("pk")
        self.assertEqual(brk, t.logged_break)
        self.assertEqual(t.type, Timestamp.BREAK)

    def test_break_form_save_assigns_timestamp(self):
        user = factories.UserFactory.create()
        t = user.timestamp_set.create(type=Timestamp.SPLIT)

        self.client.force_login(user)

        response = self.client.post(
            Break.urls["create"] + "?timestamp={}".format(t.pk),
            {
                "day": dt.date.today().isoformat(),
                "starts_at": "12:00",
                "ends_at": "12:45",
                "description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        brk = user.breaks.get()
        t.refresh_from_db()

        self.assertEqual(t.logged_break, brk)
        self.assertEqual(t.type, Timestamp.BREAK)
        self.assertEqual(Timestamp.objects.count(), 1)

        t2 = user.timestamp_set.create(type=Timestamp.SPLIT)
        response = self.client.post(
            brk.urls["update"] + "?timestamp={}".format(t2.pk),
            {
                "day": dt.date.today().isoformat(),
                "starts_at": "12:00",
                "ends_at": "12:45",
                "description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        t2.refresh_from_db()
        self.assertIsNone(t2.logged_break)  # No reassignment

    def test_update_delete_forbidden(self):
        brk = Break.objects.create(
            user=factories.UserFactory.create(),
            day=dt.date.today(),
            starts_at=dt.time(12, 0),
            ends_at=dt.time(13, 0),
        )

        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get(
            brk.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(response, "Cannot modify breaks of other users.")

        response = self.client.get(
            brk.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(response, "Cannot modify breaks of other users.")
