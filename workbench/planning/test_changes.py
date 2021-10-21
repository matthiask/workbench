import datetime as dt

from django.test import TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.middleware import set_user_name
from workbench.planning import updates


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

        pw = factories.PlannedWorkFactory.create(weeks=[dt.date.today()])
        pw.project.delete()

        c = updates.changes(since=timezone.now() - dt.timedelta(days=1))

        from pprint import pprint

        pprint(c)
