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

        updates.changes(since=timezone.now() - dt.timedelta(days=1))

    @travel("2021-10-18")
    def test_updates(self):
        """Test the planning updates functionality"""
        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(d) for d in (0, 7, 14)])
        original_pw_user = pw.user
        m = factories.MilestoneFactory.create(project=pw.project, date=dt.date.today())

        LoggedAction.objects.all().update(
            created_at=F("created_at") - dt.timedelta(days=14)
        )

        pw.user = pw.project.owned_by
        pw.hours = 50
        pw.weeks = [in_days(d) for d in (7, 14, 21)]
        pw.milestone = m
        pw.save()
        m.date = dt.date.today() + dt.timedelta(days=1)
        m.save()

        c = updates.changes(since=timezone.now() - dt.timedelta(days=1))
        self.assertEqual(set(c), {original_pw_user, pw.user})

        updates.changes_mails()
        self.assertEqual(len(mail.outbox), 2)

    @travel("2021-10-18")
    def test_absence_changes(self):
        """Absences of people one shares projects with land in the updates"""
        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(d) for d in (7, 14)])
        absence = factories.AbsenceFactory.create(
            user=pw.user,
            starts_on=in_days(7),
            ends_on=in_days(11),
            days=5,
            description="Herbstferien",
        )

        c = updates.absence_changes(since=timezone.now() - dt.timedelta(days=1))
        # The absent user and the project owner, nobody else
        self.assertEqual(set(c), {pw.user, pw.project.owned_by})

        [change] = c[pw.project.owned_by]
        self.assertEqual(change["type"], updates.CREATE)
        self.assertEqual(
            change["object"],
            f"{pw.user.get_short_name()}: vacation, 25.10.2021 - 29.10.2021 (5.00d) Herbstferien",
        )
        self.assertEqual(change["projects"], [pw.project])

        absence.ends_on = in_days(18)
        absence.days = 10
        absence.save()

        c = updates.absence_changes(since=timezone.now() - dt.timedelta(days=1))
        [change] = c[pw.project.owned_by]
        self.assertEqual(change["type"], updates.CREATE)  # Created and updated

    @travel("2021-10-18")
    def test_absence_changes_of_people_who_worked_on_the_project(self):
        """Logging hours on a project is enough to be part of the audience"""
        self.set_current_user()

        project = factories.ProjectFactory.create()
        service = factories.ServiceFactory.create(project=project)
        hours = factories.LoggedHoursFactory.create(service=service)
        factories.AbsenceFactory.create(
            user=hours.rendered_by, starts_on=in_days(3), ends_on=in_days(10), days=6
        )

        c = updates.absence_changes(since=timezone.now() - dt.timedelta(days=1))
        self.assertEqual(set(c), {hours.rendered_by, project.owned_by})
        self.assertEqual(c[project.owned_by][0]["projects"], [project])

    @travel("2021-10-18")
    def test_uninteresting_absences(self):
        """Past absences and working time corrections are skipped"""
        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(d) for d in (7, 14)])
        factories.AbsenceFactory.create(
            user=pw.user, starts_on=in_days(-20), ends_on=in_days(-10), days=8
        )
        factories.AbsenceFactory.create(
            user=pw.user,
            starts_on=in_days(7),
            days=1,
            reason=factories.Absence.CORRECTION,
        )

        self.assertEqual(
            updates.absence_changes(since=timezone.now() - dt.timedelta(days=1)), {}
        )

    @travel("2021-10-18")
    def test_absences_are_not_reported_for_suppressed_projects(self):
        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(d) for d in (7, 14)])
        pw.project.suppress_planning_update_mails = True
        pw.project.save()
        factories.AbsenceFactory.create(
            user=pw.user, starts_on=in_days(7), ends_on=in_days(11), days=5
        )

        self.assertEqual(
            updates.absence_changes(since=timezone.now() - dt.timedelta(days=1)), {}
        )

    @travel("2021-10-18")
    def test_absence_mails(self):
        """Absence changes alone are enough to produce a planning update mail"""
        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(d) for d in (7, 14)])
        # The audit trigger stamps created_at from the database clock which
        # time_machine does not freeze, so move the planning changes out of the
        # mail's window by setting an absolute timestamp.
        LoggedAction.objects.all().update(
            created_at=timezone.now() - dt.timedelta(days=14)
        )
        factories.AbsenceFactory.create(
            user=pw.user,
            starts_on=in_days(7),
            ends_on=in_days(11),
            days=5,
            description="Herbstferien",
        )

        since = updates.start_of_monday() - dt.timedelta(days=7)
        self.assertEqual(updates.changes(since=since), {})
        self.assertTrue(updates.absence_changes(since=since))

        updates.changes_mails()
        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            self.assertIn("Absenzen von Personen", message.body)
            self.assertIn("Herbstferien", message.body)

    @travel("2021-10-18")
    def test_absence_updates_and_deletions(self):
        """Updated and deleted absences are reported with all their details"""
        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(d) for d in (7, 14)])
        other = factories.PlannedWorkFactory.create(
            project=pw.project, weeks=[in_days(d) for d in (7, 14)]
        )
        absence = factories.AbsenceFactory.create(
            user=pw.user, starts_on=in_days(7), days=1, description="Brückentag"
        )
        deleted = factories.AbsenceFactory.create(
            user=other.user, starts_on=in_days(3), ends_on=in_days(5), days=3
        )
        LoggedAction.objects.all().update(
            created_at=timezone.now() - dt.timedelta(days=14)
        )

        absence.user = other.user
        absence.ends_on = in_days(9)
        absence.days = 3
        absence.reason = factories.Absence.SICKNESS
        absence.save()
        deleted.delete()

        c = updates.absence_changes(since=timezone.now() - dt.timedelta(days=1))
        self.assertEqual(set(c), {pw.user, other.user, pw.project.owned_by})

        removed, updated = sorted(
            c[pw.project.owned_by], key=lambda obj: obj["pretty_type"]
        )

        self.assertEqual(removed["type"], updates.DELETE)
        self.assertEqual(
            removed["object"],
            f"{other.user.get_short_name()}: vacation, 21.10.2021 - 23.10.2021 (3.00d)",
        )

        self.assertEqual(updated["type"], updates.UPDATE)
        changed = {row["field"]: (row["old"], row["new"]) for row in updated["changes"]}
        self.assertEqual(changed["user_id"], (pw.user, other.user))
        self.assertEqual(changed["ends_on"], ("<no value>", "27.10.2021"))
        self.assertEqual(changed["reason"], ("vacation", "sickness"))
        self.assertEqual(changed["days"], ("1.00", "3.00"))
        # Derived from the reason, not worth reporting
        self.assertNotIn("is_vacation", changed)

    @travel("2021-10-18")
    def test_absences_of_project_owners(self):
        """Owners are part of their projects' audience in both directions"""
        self.set_current_user()

        pw = factories.PlannedWorkFactory.create(weeks=[in_days(d) for d in (7, 14)])
        factories.AbsenceFactory.create(
            user=pw.project.owned_by, starts_on=in_days(7), ends_on=in_days(11), days=5
        )

        c = updates.absence_changes(since=timezone.now() - dt.timedelta(days=1))
        self.assertEqual(set(c), {pw.user, pw.project.owned_by})
        self.assertEqual(c[pw.user][0]["projects"], [pw.project])

    @travel("2021-10-18")
    def test_absences_of_owners_of_dormant_projects(self):
        """Owning a project nobody works on doesn't put anyone in the audience"""
        self.set_current_user()

        project = factories.ProjectFactory.create()
        factories.AbsenceFactory.create(
            user=project.owned_by, starts_on=in_days(7), ends_on=in_days(11), days=5
        )

        self.assertEqual(
            updates.absence_changes(since=timezone.now() - dt.timedelta(days=1)), {}
        )
