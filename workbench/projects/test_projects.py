from datetime import date

from django.test import TestCase

from workbench import factories
from workbench.projects.models import Project


class ProjectsTest(TestCase):
    def test_create(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)
        person = factories.PersonFactory(
            organization=factories.OrganizationFactory.create()
        )

        response = self.client.post(
            "/projects/create/",
            {
                # "customer": person.organization.pk,  automatic
                "contact": person.pk,
                "title": "Test project",
                "owned_by": user.pk,
                "type": Project.INTERNAL,
            },
        )
        project = Project.objects.get()
        self.assertEqual(project.customer, person.organization)
        self.assertEqual(project.contact, person)
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
                # "effort_rate": "180",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "Entweder alle Felder einfüllen oder keine.")

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

        self.assertRedirects(
            self.client.get(service1.urls["detail"]), project.urls["services"]
        )
        response = self.client.post(
            service1.urls["update"],
            {
                "title": "Production service",
                "effort_type": "Consulting",
                "effort_rate": "200",
                "effort_hours": 20,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)
        service1.refresh_from_db()
        self.assertAlmostEqual(service1.service_cost, 4000)

        response = self.client.post(
            service1.urls["delete"],
            {"merge_into": service2.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(list(project.services.all()), [service2])

    def test_autofill(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["createservice"])
        self.assertContains(response, 'data-autofill="{}"')

        factories.service_types()

        response = self.client.get(project.urls["createservice"])
        self.assertContains(response, "&quot;effort_type&quot;: &quot;consulting&quot;")
        self.assertContains(response, "&quot;effort_rate&quot;: 250")

    def test_delete(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["delete"])
        self.assertEqual(response.status_code, 200)

        factories.LoggedCostFactory.create(project=project)

        response = self.client.get(project.urls["delete"])
        self.assertRedirects(response, project.urls["services"])

    def test_create_validation(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.post(
            "/projects/create/",
            {"title": "Test project", "owned_by": user.pk, "type": Project.INTERNAL},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            dict(response.context_data["form"].errors),
            {"customer": ["Dieses Feld ist zwingend erforderlich."]},
        )

        org = factories.OrganizationFactory.create()
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )

        response = self.client.post(
            "/projects/create/",
            {
                "customer": org.pk,
                "contact": person.pk,
                "title": "Test project",
                "owned_by": user.pk,
                "type": Project.INTERNAL,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            dict(response.context_data["form"].errors),
            {
                "contact": [
                    "Der Kontakt Vorname Nachname / The Organization Ltd"
                    " gehört nicht zu The Organization Ltd."
                ]
            },
        )

    def test_list(self):
        project = factories.ProjectFactory.create()
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def valid(p):
            self.assertEqual(self.client.get("/projects/?" + p).status_code, 200)

        valid("")
        valid("s=all")
        valid("s=closed")
        valid("org={}".format(project.customer_id))
        valid("type=internal")
        valid("type=maintenance")
        valid("owned_by={}".format(user.id))
        valid("owned_by=0")  # only inactive

    def test_project_detail_redirect(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        self.assertRedirects(
            self.client.get(project.urls["detail"]), project.urls["overview"]
        )

    def test_update(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["create"])
        self.assertNotContains(response, "is_closed")

        response = self.client.get(project.urls["update"])
        self.assertContains(response, "is_closed")

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                "is_closed": "on",
            },
        )
        self.assertRedirects(response, project.urls["overview"])
        project.refresh_from_db()
        self.assertEqual(project.closed_on, date.today())

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                "is_closed": "",
            },
        )
        self.assertRedirects(response, project.urls["services"])
        project.refresh_from_db()
        self.assertIsNone(project.closed_on)

    def test_copy(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(
            project.urls["create"] + "?copy_project=" + str(project.pk)
        )
        self.assertContains(response, 'value="{}"'.format(project.title))
        # print(response, response.content.decode("utf-8"))
