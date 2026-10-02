import datetime as dt
from decimal import Decimal

from django.test import TestCase
from time_machine import travel

from workbench import factories
from workbench.accounts.models import User
from workbench.logbook.celebrations import SESSION_KEY, project_emoji
from workbench.projects.models import InternalType, Project
from workbench.tools.forms import WarningsForm


class CelebrationsTest(TestCase):
    def test_project_emoji(self):
        """Emojis depend on the project type and the internal type"""
        project = Project(type=Project.ORDER)
        self.assertEqual(project_emoji(project), "✅")

        project = Project(type=Project.MAINTENANCE)
        self.assertEqual(project_emoji(project), "🔧")

        project = Project(type=Project.INTERNAL)
        self.assertEqual(project_emoji(project), "✨")

        project.internal_type = InternalType(name="Controlling", percentage=0)
        self.assertEqual(project_emoji(project), "📊")

        project.internal_type = InternalType(name="Something new", percentage=0)
        self.assertEqual(project_emoji(project), "✨")

    def test_celebration_after_logging(self):
        """The celebration is shown once on the page after logging hours"""
        service = factories.ServiceFactory.create(project__type=Project.MAINTENANCE)
        user = service.project.owned_by
        self.client.force_login(user)

        def send(**kwargs):
            data = {
                "modal-rendered_by": user.pk,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-service": service.id,
                "modal-hours": "0.5",
                "modal-description": "Test",
            }
            data.update({f"modal-{key}": value for key, value in kwargs.items()})
            return self.client.post(
                service.project.urls["createhours"],
                data,
                headers={"x-requested-with": "XMLHttpRequest"},
            )

        response = send()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.client.session[SESSION_KEY],
            {"emoji": "🔧", "message": None, "confetti": False, "rings_from": {}},
        )

        response = self.client.get("/")
        self.assertContains(response, '<span class="celebration-emoji">🔧</span>')
        self.assertNotIn(SESSION_KEY, self.client.session)

        response = self.client.get("/")
        self.assertNotContains(response, "celebration-emoji")

    def test_no_celebration_for_others(self):
        """Logging hours for someone else doesn't celebrate"""
        service = factories.ServiceFactory.create()
        other = factories.UserFactory.create()
        self.client.force_login(service.project.owned_by)

        response = self.client.post(
            service.project.urls["createhours"],
            {
                "modal-rendered_by": other.pk,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-service": service.id,
                "modal-hours": "0.5",
                "modal-description": "Test",
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_hours_targets(self):
        """Daily and weekly targets follow the working time model and employment"""
        user = factories.UserFactory.create()
        self.assertIsNone(user.daily_hours_target)
        self.assertIsNone(user.hours["today_target"])
        self.assertIsNone(user.hours["week_target"])

        factories.YearFactory.create(
            working_time_model=user.working_time_model, working_time_per_day=8.4
        )
        factories.EmploymentFactory.create(user=user, percentage=80)

        user = User.objects.get(pk=user.pk)
        self.assertEqual(user.hours["today_target"], Decimal("6.7"))
        self.assertEqual(user.hours["week_target"], Decimal("33.5"))

        factories.LoggedHoursFactory.create(rendered_by=user, hours=7)
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertContains(response, 'class="hours-ring complete"')
        self.assertContains(response, "stroke-dasharray: 20.9 100")

    @travel("2026-09-30 12:00")  # Wednesday
    def test_milestones(self):
        """Milestones are celebrated when crossing 50% and 100%"""
        service = factories.ServiceFactory.create()
        user = service.project.owned_by
        factories.YearFactory.create(
            working_time_model=user.working_time_model, working_time_per_day=8
        )
        factories.EmploymentFactory.create(user=user, date_from=dt.date(2026, 1, 1))
        self.client.force_login(user)

        def send(hours, rendered_on=dt.date(2026, 9, 30)):
            response = self.client.post(
                service.project.urls["createhours"],
                {
                    "modal-rendered_by": user.pk,
                    "modal-rendered_on": rendered_on.isoformat(),
                    "modal-service": service.id,
                    "modal-hours": hours,
                    "modal-description": f"Test {hours} {rendered_on}",
                    WarningsForm.ignore_warnings_id: "take-a-break",
                },
                headers={"x-requested-with": "XMLHttpRequest"},
            )
            self.assertEqual(response.status_code, 201)
            return self.client.session.pop(SESSION_KEY)

        celebration = send("2")
        self.assertIsNone(celebration["message"])
        self.assertEqual(celebration["rings_from"], {"today": 0.0, "week": 0.0})

        celebration = send("2.5")
        self.assertEqual(celebration["message"], "Halfway there 💪")
        self.assertFalse(celebration["confetti"])
        self.assertEqual(celebration["rings_from"], {"today": 25.0, "week": 5.0})

        celebration = send("1")
        self.assertIsNone(celebration["message"])

        celebration = send("3")
        self.assertEqual(celebration["message"], "Day complete 🎉")
        self.assertTrue(celebration["confetti"])

        celebration = send("1")
        self.assertIsNone(celebration["message"])

        # Hours on another day of the week only count towards the week
        celebration = send("10", rendered_on=dt.date(2026, 9, 29))
        self.assertIsNone(celebration["message"])
        celebration = send("21", rendered_on=dt.date(2026, 9, 28))
        self.assertEqual(celebration["message"], "Week complete 🏁")
        self.assertTrue(celebration["confetti"])
