import datetime as dt

from django.core import mail
from django.db.models import F
from django.test import TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from time_machine import travel

from workbench import factories
from workbench.accounts.middleware import set_user_name
from workbench.audit.models import LoggedAction
from workbench.planning import updates
from workbench.tools.validation import in_days


class ChangesTest(TestCase):
    def setUp(self):
        deactivate_all()

    def set_current_user(self):
        user = factories.UserFactory.create()
        set_user_name(f"user-{user.pk}-{user.get_short_name()}")
        return user

    def test_deleted_project_changes(self):
        """Deleted projects and work still appears in the view"""

        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(0)])
        pw.project.delete()

        c = updates.changes(since=timezone.now() - dt.timedelta(days=1))

        from pprint import pprint

        pprint(c)

    @travel("2021-10-18")
    def test_updates(self):
        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(d) for d in (0, 7, 14)])
        original_pw_user = pw.user
        m = factories.MilestoneFactory.create(project=pw.project, date=dt.date.today())

        LoggedAction.objects.all().update(
            created_at=F("created_at") - dt.timedelta(days=10)
        )

        pw.user = pw.project.owned_by
        pw.hours = 50
        pw.weeks = [in_days(d) for d in (7, 14, 21)]
        pw.save()
        m.date = dt.date.today() + dt.timedelta(days=1)
        m.save()

        c = updates.changes(since=timezone.now() - dt.timedelta(days=1))
        self.assertEqual(set(c), {original_pw_user, pw.user})

        from pprint import pprint

        pprint(c)

        updates.changes_mails()
        self.assertEqual(len(mail.outbox), 2)
