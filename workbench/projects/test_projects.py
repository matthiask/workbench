from django.test import TestCase

from workbench import factories
from workbench.projects.models import Project


class ProjectsTest(TestCase):
    def test_create(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.post(
            "/projects/create/",
            {
                "customer": factories.OrganizationFactory.create().pk,
                "title": "Test project",
                "owned_by": user.pk,
                "type": Project.INTERNAL,
            },
        )
        project = Project.objects.get()
        self.assertRedirects(response, project.urls["services"])

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Consulting service",
                "effort_type": "Consulting",
                "effort_rate": "180",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Production service",
                "effort_type": "Production",
                "effort_rate": "180",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        service1, service2 = project.services.all()

        service1.loggedcosts.create(created_by=user, cost=10, project=project)

        self.assertRedirects(
            self.client.get(service1.urls["move"] + "?down"), project.urls["services"]
        )
        self.assertEqual(list(project.services.all()), [service2, service1])

        response = self.client.post(
            service1.urls["delete"],
            {"merge_into": service2.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(list(project.services.all()), [service2])
