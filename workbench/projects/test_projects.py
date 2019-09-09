from datetime import date

from django.test import TestCase

from workbench import factories
from workbench.projects.models import Project, Service
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import messages


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
        self.assertRedirects(response, project.urls["detail"])

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Consulting service",
                "effort_type": "Consulting",
                "effort_rate": "180",
                "allow_logging": True,
                WarningsForm.ignore_warnings_id: "no-role-selected",
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
                "allow_logging": True,
                WarningsForm.ignore_warnings_id: "no-role-selected",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "Either fill in all fields or none.")

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Production service",
                # "effort_type": "Production",
                "effort_rate": "180",
                "third_party_costs": "20",
                "allow_logging": True,
                WarningsForm.ignore_warnings_id: "no-role-selected",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "Either fill in all fields or none.")
        self.assertContains(response, "Cannot be empty if third party costs is set.")

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Production service",
                "effort_type": "Production",
                "effort_rate": "180",
                "allow_logging": True,
                WarningsForm.ignore_warnings_id: "no-role-selected",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        service1, service2 = project.services.all()

        service1.loggedcosts.create(
            created_by=user, rendered_by=user, cost=10, project=project
        )

        response = self.client.post(
            "/projects/service/set-order/", {"ids[]": [service2.id, service1.id]}
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(list(project.services.all()), [service2, service1])

        self.assertRedirects(
            self.client.get(service1.urls["detail"]), project.urls["detail"]
        )
        response = self.client.post(
            service1.urls["update"],
            {
                "title": "Production service",
                "effort_type": "Consulting",
                "effort_rate": "200",
                "effort_hours": 20,
                WarningsForm.ignore_warnings_id: "no-role-selected",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)
        service1.refresh_from_db()
        self.assertAlmostEqual(service1.service_cost, 4000)

        response = self.client.post(
            service1.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(project.services.all()), {service1, service2})

        self.assertEqual(service1.loggedcosts.count(), 1)
        self.assertEqual(service2.loggedcosts.count(), 0)
        response = self.client.post(
            service1.urls["reassign_logbook"],
            {"service": service2.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        self.assertEqual(service1.loggedcosts.count(), 0)
        self.assertEqual(service2.loggedcosts.count(), 1)

        response = self.client.post(
            service1.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(set(project.services.all()), {service2})

    def test_service_with_rate_zero(self):
        Service(
            project=factories.ProjectFactory.create(),
            title="Any",
            effort_type="Any",
            effort_rate=0,
        ).full_clean()

    def test_service_deletion_without_merge(self):
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)
        response = self.client.get(
            service.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertNotContains(response, "merge_into")

        response = self.client.post(
            service.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            messages(response), ["service 'Any service' has been deleted successfully."]
        )
        self.assertEqual(Service.objects.count(), 0)

    def test_autofill(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(
            project.urls["createservice"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(response, 'data-autofill="{}"')

        factories.service_types()

        response = self.client.get(
            project.urls["createservice"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(response, "&quot;effort_type&quot;: &quot;consulting&quot;")
        self.assertContains(response, "&quot;effort_rate&quot;: 250")

    def test_delete(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["delete"])
        self.assertEqual(response.status_code, 200)

        factories.LoggedCostFactory.create(project=project)

        response = self.client.get(project.urls["delete"])
        self.assertRedirects(response, project.urls["detail"])

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
            {"customer": ["This field is required."]},
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
                    "The contact Vorname Nachname / The Organization Ltd"
                    " does not belong to The Organization Ltd."
                ]
            },
        )

    def test_lists(self):
        project = factories.ProjectFactory.create()
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def valid(p):
            self.assertEqual(self.client.get("/projects/?" + p).status_code, 200)

        valid("")
        valid("q=test")
        valid("s=all")
        valid("s=closed")
        valid("s=no-invoices")
        valid("s=accepted-offers")
        valid("s=accepted-offers-no-invoices")
        valid("org={}".format(project.customer_id))
        valid("type=internal")
        valid("type=maintenance")
        valid("owned_by={}".format(user.id))
        valid("owned_by=0")  # only inactive

    def test_autocomplete(self):
        project = factories.ProjectFactory.create(closed_on=date.today())
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get("/contacts/organizations/autocomplete/")
        self.assertEqual(response.json(), {"results": []})
        response = self.client.get("/contacts/organizations/autocomplete/?q=")
        self.assertEqual(response.json(), {"results": []})
        response = self.client.get("/contacts/organizations/autocomplete/?q=Orga")
        self.assertEqual(
            response.json(),
            {
                "results": [
                    {"label": "The Organization Ltd", "value": project.customer_id}
                ]
            },
        )

        self.assertEqual(
            self.client.get("/projects/autocomplete/?q=proj").json(),
            {"results": [{"label": str(project), "value": project.id}]},
        )

        self.assertEqual(
            self.client.get("/projects/autocomplete/?q=proj&only_open=on").json(),
            {"results": []},
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
        self.assertRedirects(response, project.urls["detail"])
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
        self.assertRedirects(response, project.urls["detail"])
        project.refresh_from_db()
        self.assertIsNone(project.closed_on)

    def test_customer_update(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        invoice = factories.InvoiceFactory.create(
            project=project, customer=project.customer, contact=project.contact
        )
        new_org = factories.OrganizationFactory.create()
        new_person = factories.PersonFactory.create(organization=new_org)

        response = self.client.post(
            project.urls["update"],
            {
                "customer": new_org.id,
                "contact": new_person.pk,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
            },
        )
        self.assertContains(
            response,
            "This project already has invoices. The invoices&#39;"
            " customer record will be changed too.",
        )
        response = self.client.post(
            project.urls["update"],
            {
                "customer": new_org.id,
                "contact": new_person.pk,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                WarningsForm.ignore_warnings_id: "customer-update-but-already-invoices",
            },
        )
        self.assertRedirects(response, project.urls["detail"])

        project.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(project.customer, new_org)
        self.assertEqual(invoice.customer, new_org)

    def test_copy(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["create"] + "?copy=" + str(project.pk))
        self.assertContains(response, 'value="{}"'.format(project.title))
        # print(response, response.content.decode("utf-8"))

        response = self.client.get(project.urls["create"] + "?copy=blub")
        self.assertEqual(response.status_code, 200)  # No crash

    def test_move(self):
        project = factories.ProjectFactory.create()
        closed = factories.ProjectFactory.create(closed_on=date.today())
        service = factories.ServiceFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            service.urls["move"],
            {"project": closed.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "This project is already closed.")

        response = self.client.post(
            service.urls["move"],
            {"project": project.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        service.refresh_from_db()
        self.assertEqual(service.project, project)

    def test_select(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["select"])
        self.assertContains(
            response, 'data-autocomplete-url="/projects/autocomplete/?only_open=on"'
        )

        response = self.client.post(
            project.urls["select"], {"project-project": project.pk}
        )
        self.assertEqual(response.status_code, 299)
        self.assertEqual(response.json(), {"redirect": project.get_absolute_url()})

    def test_services_api(self):
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        response = self.client.get(service.project.urls["services"])
        self.assertEqual(response["content-type"], "application/json")
