import datetime as dt
from decimal import Decimal

from django.core import mail
from django.test import TestCase

from freezegun import freeze_time

from workbench import factories
from workbench.reporting.accounting import send_accounting_files
from workbench.reporting.models import Accruals


class ReportingTest(TestCase):
    def test_send_accounting_files(self):
        factories.UserFactory.create(is_admin=True)
        factories.ProjectFactory.create()

        with freeze_time("2019-12-26"):
            send_accounting_files()
            self.assertEqual(len(mail.outbox), 0)

        with freeze_time("2020-01-01"):
            send_accounting_files()
            self.assertEqual(len(mail.outbox), 1)

    def test_accruals(self):
        self.assertEqual(
            Accruals.objects.for_cutoff_date(dt.date.today()).accruals, Decimal("0.00")
        )
