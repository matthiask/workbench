import datetime as dt

from django.test import TestCase

from workbench import factories
from workbench.logbook.celebrations import SESSION_KEY, project_emoji
from workbench.projects.models import InternalType, Project


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
        self.assertEqual(self.client.session[SESSION_KEY], {"emoji": "🔧"})

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
