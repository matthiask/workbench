from datetime import date, timedelta

from django.test import TestCase

from workbench import factories
from workbench.logbook.models import LoggedHours
from workbench.tools.formats import local_date_format


class LogbookTest(TestCase):
    def test_create_logged_hours(self):
        service = factories.ServiceFactory.create()
        project = service.project
        self.client.force_login(project.owned_by)

        def send(**kwargs):
            return self.client.post(
                project.urls["createhours"],
                {
                    "rendered_by": project.owned_by_id,
                    "rendered_on": local_date_format(date.today()),
                    "service": service.id,
                    "hours": "0.1",
                    "description": "Test",
                    **kwargs,
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        response = send()
        self.assertEqual(response.status_code, 201)

        response = send()
        self.assertContains(response, "Scheint ein Duplikat zu sein.")

        response = send(
            rendered_on=local_date_format(date.today() - timedelta(days=10))
        )
        self.assertContains(
            response, "Stunden müssen in der gleichen Woche erfasst werden."
        )

        response = send(
            rendered_on=local_date_format(date.today() + timedelta(days=10))
        )
        self.assertContains(response, "Tut mir leid, zu früh.")

    def test_no_same_week_logging(self):
        service = factories.ServiceFactory.create()
        project = service.project
        user = factories.UserFactory.create(enforce_same_week_logging=False)

        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createhours"],
            {
                "rendered_by": user.id,
                "rendered_on": local_date_format(date.today() - timedelta(days=10)),
                "service": service.id,
                "hours": "0.1",
                "description": "Test",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

    def test_log_and_create_service(self):
        project = factories.ProjectFactory.create()

        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createhours"],
            {
                "rendered_by": project.owned_by_id,
                "rendered_on": local_date_format(date.today()),
                # "service": service.id,
                "hours": "0.1",
                "description": "Test",
                "service_title": "service title",
                "service_description": "service description",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        entry = LoggedHours.objects.get()
        self.assertEqual(entry.service.title, "service title")
