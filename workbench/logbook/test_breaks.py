import datetime as dt

from django.core.exceptions import ValidationError
from django.test import TestCase

from freezegun import freeze_time

from workbench import factories
from workbench.logbook.models import Break


class BeaksTest(TestCase):
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
    def test_break_form(self):
        self.client.force_login(factories.UserFactory.create())

        response = self.client.get(Break.urls["create"])
        self.assertContains(response, 'value="2020-01-02"')
