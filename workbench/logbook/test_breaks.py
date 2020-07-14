import datetime as dt

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from time_machine import travel

from workbench import factories
from workbench.logbook.models import Break
from workbench.timer.models import Timestamp
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code
from workbench.tools.validation import in_days


def c(day, time):
    return timezone.make_aware(dt.datetime.combine(day, time))


class BreaksTest(TestCase):
    def test_list(self):
        """Filter form smoke test"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        brk = Break.objects.create(
            user=factories.UserFactory.create(),
            starts_at=c(dt.date.today(), dt.time(12, 0)),
            ends_at=c(dt.date.today(), dt.time(13, 0)),
        )

        code = check_code(self, "/logbook/breaks/")
        code("")
        code("user=-1")
        code("user={}".format(user.pk))
        code("export=xlsx")

        response = self.client.get(brk.urls["detail"])
        self.assertContains(response, str(brk))

    def test_valid_break(self):
        """Model validation of a valid break raises no exceptions"""
        brk = Break(
            user=factories.UserFactory.create(),
            starts_at=c(dt.date.today(), dt.time(12, 0)),
            ends_at=c(dt.date.today(), dt.time(13, 0)),
        )
        brk.full_clean()
        self.assertEqual(brk.timedelta.total_seconds(), 3600)

    def test_break_validation(self):
        """Model validation of an invalid break fails"""
        with self.assertRaises(ValidationError) as cm:
            Break(
                user=factories.UserFactory.create(),
                starts_at=c(dt.date.today(), dt.time(12, 0)),
                ends_at=c(dt.date.today(), dt.time(11, 0)),
            ).full_clean()

        self.assertEqual(
            list(cm.exception),
            [("ends_at", ["Breaks should end later than they begin."])],
        )

        with self.assertRaises(ValidationError) as cm:
            Break(
                user=factories.UserFactory.create(),
                starts_at=c(dt.date(2020, 1, 1), dt.time(12, 0)),
                ends_at=c(dt.date.today(), dt.time(11, 0)),
            ).full_clean()

        self.assertEqual(
            list(cm.exception),
            [("ends_at", ["Breaks must start and end on the same day."])],
        )

    @travel("2020-01-02 12:00")
    def test_break_form_initial(self):
        """Fields are initialized as expected"""
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
            created_at=timezone.now() - dt.timedelta(days=1), type=Timestamp.STOP
        )

        response = self.client.get(Break.urls["create"])
        self.assertContains(response, 'value="2020-01-02"')
        self.assertNotContains(response, 'value="2020-01-01"')

    def test_break_from_timestamps(self):
        """The breaks form URL contains expected values when using timestamps"""
        user = factories.UserFactory.create()
        now = timezone.localtime(timezone.now()).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        user.timestamp_set.create(type=Timestamp.STOP, created_at=now)
        user.timestamp_set.create(
            type=Timestamp.STOP, created_at=now - dt.timedelta(seconds=900)
        )

        self.client.force_login(user)

        response = self.client.get("/timestamps/")
        self.assertContains(response, "starts_at=08%3A45%3A00")
        self.assertContains(response, "ends_at=09%3A00%3A00")

    def test_day_validation(self):
        """Some day values are not allowed"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.post(
            Break.urls["create"],
            {
                "modal-day": "",
                "modal-starts_at": "12:00",
                "modal-ends_at": "12:45",
                "modal-description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "This field is required.")

        response = self.client.post(
            Break.urls["create"],
            {
                "modal-day": dt.date.today().isoformat(),
                "modal-starts_at": "12:00",
                "modal-ends_at": "12",
                "modal-description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "Enter a valid time.")

        response = self.client.post(
            Break.urls["create"],
            {
                "modal-day": "2010-01-01",
                "modal-starts_at": "12:00",
                "modal-ends_at": "12:45",
                "modal-description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "Breaks have to be logged promptly.")

        response = self.client.post(
            Break.urls["create"],
            {
                "modal-day": "9999-01-01",
                "modal-starts_at": "12:00",
                "modal-ends_at": "12:45",
                "modal-description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "That&#x27;s too far in the future.")

        response = self.client.post(
            Break.urls["create"],
            {
                "modal-day": dt.date.today().isoformat(),
                "modal-starts_at": "12:00",
                "modal-ends_at": "12:45",
                "modal-description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

    def test_break_form_save_assigns_timestamp(self):
        """Creating a break from the timestamps button sets the logged_break attr"""
        user = factories.UserFactory.create()
        t = user.timestamp_set.create(type=Timestamp.STOP)

        self.client.force_login(user)

        response = self.client.post(
            Break.urls["create"] + "?timestamp={}".format(t.pk),
            {
                "modal-day": dt.date.today().isoformat(),
                "modal-starts_at": "12:00",
                "modal-ends_at": "12:45",
                "modal-description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        brk = user.breaks.get()
        t.refresh_from_db()

        self.assertEqual(t.logged_break, brk)
        self.assertEqual(t.type, Timestamp.STOP)  # Type hasn't changed
        self.assertEqual(Timestamp.objects.count(), 1)

        t2 = user.timestamp_set.create(type=Timestamp.STOP)
        response = self.client.post(
            brk.urls["update"] + "?timestamp={}".format(t2.pk),
            {
                "modal-day": dt.date.today().isoformat(),
                "modal-starts_at": "12:00",
                "modal-ends_at": "12:45",
                "modal-description": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        t2.refresh_from_db()
        self.assertIsNone(t2.logged_break)  # No reassignment

    def test_update_delete_forbidden(self):
        """Updating and deleting of others' breaks is not allowed"""
        brk = Break.objects.create(
            user=factories.UserFactory.create(),
            starts_at=c(dt.date.today(), dt.time(12, 0)),
            ends_at=c(dt.date.today(), dt.time(13, 0)),
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

    def test_break_warning(self):
        """Various places show a take-a-break warning if too much work and no break"""
        service = factories.ServiceFactory.create()
        user = service.project.owned_by
        self.client.force_login(user)

        factories.LoggedHoursFactory.create(rendered_by=user, hours=5)
        Break.objects.create(
            user=user,
            starts_at=c(dt.date.today(), dt.time(12, 0)),
            ends_at=c(dt.date.today(), dt.time(12, 5)),
        )

        data = {
            "modal-rendered_by": user.id,
            "modal-rendered_on": dt.date.today().isoformat(),
            "modal-service": service.id,
            "modal-hours": "2.0",
            "modal-description": "Test",
        }

        with override_settings(FEATURES={"skip_breaks": False}):
            response = self.client.post(
                service.project.urls["createhours"],
                data,
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertContains(response, "You should take")

            self.assertIsNotNone(user.take_a_break_warning(add=10))
            self.assertIsNotNone(user.take_a_break_warning(add=3))
            self.assertIsNotNone(user.take_a_break_warning(add=1))
            self.assertIsNone(user.take_a_break_warning(add=0))

            self.assertIsNone(user.take_a_break_warning(add=1, day=in_days(-1)))

            response = self.client.post(
                service.project.urls["createhours"],
                {**data, WarningsForm.ignore_warnings_id: "take-a-break"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(response.status_code, 201)

        # With skip_breaks=True, everything just works
        response = self.client.post(
            service.project.urls["createhours"],
            {**data, "modal-hours": "3.0"},  # No duplicate
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        # Now the message also appears by default
        with override_settings(FEATURES={"skip_breaks": False}):
            response = self.client.get("/")
            self.assertContains(response, "You should take")
