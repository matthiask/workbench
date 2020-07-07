import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.contacts.models import Organization
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code, messages
from workbench.tools.validation import in_days


class ProjectsTest(TestCase):
    def test_create(self):
        """Create a project and create, update, delete and merge a few services"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        person = factories.PersonFactory(
            organization=factories.OrganizationFactory.create()
        )

        response = self.client.post(
            Project.urls["create"],
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

        service1.loggedcosts.create(created_by=user, rendered_by=user, cost=10)

        response = self.client.post(
            Service.urls["set_order"], {"ids[]": [service2.id, service1.id]}
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(list(project.services.all()), [service2, service1])

        self.assertRedirects(
            self.client.get(service1.urls["detail"]),
            "%s#service%s" % (project.urls["detail"], service1.pk),
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
            service1.urls["reassign_logbook"],
            {"service": service2.pk, "try_delete": "on"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(set(project.services.all()), {service2})

    def test_try_delete_available(self):
        """The try_delete box is only available if service isn't bound to an offer"""
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        response = self.client.get(
            service.urls["reassign_logbook"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(response, "try_delete")
        offer = factories.OfferFactory.create(
            project=service.project, status=Offer.ACCEPTED
        )
        service.offer = offer
        service.save()
        response = self.client.get(
            service.urls["reassign_logbook"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertNotContains(response, "try_delete")

    def test_service_with_rate_zero(self):
        """Services with 0/h rate are allowed (since effort_rate is Falsy)"""
        Service(
            project=factories.ProjectFactory.create(),
            title="Any",
            effort_type="Any",
            effort_rate=0,
        ).full_clean()

    def test_autofill(self):
        """Required autofilling attributes for service types are available"""
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
        """Attempting to delete a project with logged costs redirects immediately"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["delete"])
        self.assertEqual(response.status_code, 200)

        factories.LoggedCostFactory.create(
            service=factories.ServiceFactory.create(project=project)
        )

        response = self.client.get(project.urls["delete"])
        self.assertRedirects(response, project.urls["detail"])

    def test_create_validation(self):
        """Creating projects requires consistent and complete data"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.post(
            Project.urls["create"],
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
            Project.urls["create"],
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
                    "The contact Vorname Nachname"
                    " does not belong to The Organization Ltd."
                ]
            },
        )

    def test_lists(self):
        """Filter form smoke test"""
        project = factories.ProjectFactory.create()
        user = factories.UserFactory.create()
        self.client.force_login(user)

        code = check_code(self, Project.urls["list"])
        code("")
        code("q=test")
        code("s=all")
        code("s=closed")
        code("s=no-invoices")
        code("s=accepted-offers")
        code("s=accepted-offers-no-invoices")
        code("s=solely-declined-offers")
        code("s=old-projects")
        code("s=invalid-customer-contact-combination")
        code("org={}".format(project.customer_id))
        code("type=internal")
        code("type=maintenance")
        code("owned_by={}".format(user.id))
        code("owned_by=-1")  # mine
        code("owned_by=0")  # only inactive

        code("invalid=3", 302)

    def test_invalid_search_form(self):
        """Invalid filter form redirect test"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.get(Project.urls["list"] + "?org=0")
        self.assertRedirects(response, Project.urls["list"] + "?error=1")
        self.assertEqual(messages(response), ["Search form was invalid."])

    def test_autocomplete(self):
        """Test the autocomplete endpoints of contacts and projects"""
        project = factories.ProjectFactory.create(closed_on=dt.date.today())
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get(Organization.urls["autocomplete"])
        self.assertEqual(response.json(), {"results": []})
        response = self.client.get(Organization.urls["autocomplete"] + "?q=")
        self.assertEqual(response.json(), {"results": []})
        response = self.client.get(Organization.urls["autocomplete"] + "?q=Orga")
        self.assertEqual(
            response.json(),
            {
                "results": [
                    {"label": "The Organization Ltd", "value": project.customer_id}
                ]
            },
        )

        self.assertEqual(
            self.client.get(Project.urls["autocomplete"] + "?q=proj").json(),
            {"results": [{"label": str(project), "value": project.id}]},
        )

        self.assertEqual(
            self.client.get(
                Project.urls["autocomplete"] + "?q=proj&only_open=on"
            ).json(),
            {"results": []},
        )

    def test_customer_update(self):
        """Updating customers of projects reassigns invoices (after asking)"""
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
            "This project already has invoices. The invoices&#x27;"
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
        """Copying projects works"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["create"] + "?copy=" + str(project.pk))
        self.assertContains(response, 'value="{}"'.format(project.title))
        self.assertNotContains(response, "closed_on")
        # print(response, response.content.decode("utf-8"))

        response = self.client.get(project.urls["create"] + "?copy=blub")
        self.assertEqual(response.status_code, 200)  # No crash

    def test_move(self):
        """Moving services to other projects works and also handles flat rates"""
        project = factories.ProjectFactory.create()
        closed = factories.ProjectFactory.create(closed_on=dt.date.today())
        flat_rate = factories.ProjectFactory.create(flat_rate=100)
        service = factories.ServiceFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            service.urls["move"],
            {"modal-project": closed.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "This project is already closed.")

        response = self.client.post(
            service.urls["move"],
            {"modal-project": flat_rate.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, 'value="new-project-has-flat-rate"')

        response = self.client.post(
            service.urls["move"],
            {"modal-project": project.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        service.refresh_from_db()
        self.assertEqual(service.project, project)
        self.assertEqual(service.effort_rate, None)

        response = self.client.post(
            service.urls["move"],
            {
                "modal-project": flat_rate.pk,
                WarningsForm.ignore_warnings_id: "new-project-has-flat-rate",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        service.refresh_from_db()
        self.assertEqual(service.effort_rate, 100)

    def test_select(self):
        """Test the project select modal"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["select"])
        self.assertRedirects(response, "/")

        response = self.client.get(
            project.urls["select"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            'data-autocomplete-url="{}?only_open=on"'.format(
                Project.urls["autocomplete"]
            ),
        )

        response = self.client.post(
            project.urls["select"],
            {"modal-project": project.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 299)
        self.assertEqual(response.json(), {"redirect": project.get_absolute_url()})

    def test_services_api(self):
        """The services API returns JSON with the expected format"""
        service = factories.ServiceFactory.create()
        offer = factories.OfferFactory.create(project=service.project)
        factories.ServiceFactory.create(project=service.project, offer=offer)

        self.client.force_login(service.project.owned_by)

        response = self.client.get(service.project.urls["services"])
        self.assertEqual(response["content-type"], "application/json")

        services = response.json()["services"]
        self.assertEqual(len(services), 2)
        self.assertIn(offer.code, services[0]["label"])
        self.assertEqual(services[1]["label"], "Not offered yet")

    def test_projects_api(self):
        """The projects API returns JSON"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.get(Project.urls["projects"])
        self.assertEqual(response["content-type"], "application/json")

    def test_assign_service_types(self):
        """The assign services type endpoint works and redirects"""
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        service_types = factories.service_types()
        response = self.client.get(
            service.urls["assign_service_type"]
            + "?service_type={}".format(service_types.consulting.pk)
        )
        self.assertRedirects(response, service.get_absolute_url())

        service.refresh_from_db()
        self.assertEqual(service.effort_type, "consulting")
        self.assertEqual(service.effort_rate, 250)

    def test_create_services_with_flat_rates(self):
        """Projects with flat rates do not allow changing effort rates on services"""
        project = factories.ProjectFactory.create(flat_rate=250)
        self.client.force_login(project.owned_by)

        response = self.client.get(
            project.urls["createservice"],
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        # print(response.content.decode("utf-8"))

        self.assertContains(
            response,
            '<input type="number" name="effort_rate" value="250.00" step="0.01" class="form-control" disabled id="id_effort_rate">',  # noqa
            html=True,
        )
        self.assertContains(
            response,
            '<input type="text" name="effort_type" value="Pauschalsatz" maxlength="50" class="form-control" disabled id="id_effort_type">',  # noqa
            html=True,
        )
        self.assertNotContains(response, 'id="id_service_type"')

    def test_add_flat_rate_to_existing_project(self):
        """Adding a flat rate to a project with services warns about
        overridding their effort rate"""
        project = factories.ServiceFactory.create().project
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                "flat_rate": 250,
            },
        )
        self.assertContains(response, 'value="flat-rate-but-already-services"')

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                "flat_rate": 250,
                WarningsForm.ignore_warnings_id: "flat-rate-but-already-services",
            },
        )
        self.assertRedirects(response, project.urls["detail"])

        service = project.services.get()
        self.assertEqual(service.effort_rate, 250)
        self.assertEqual(service.effort_type, "Pauschalsatz")

    @override_settings(FEATURES={"glassfrog": False})
    def test_no_role(self):
        """The service form has no role field when not GLASSFROG"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(
            project.urls["createservice"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertNotContains(response, "id_role")

    def test_no_flat_rate(self):
        """Uses without CONTROLLING do not see the flat rate field"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["update"])
        self.assertContains(response, "id_flat_rate")

        with override_settings(FEATURES={"controlling": False}):
            response = self.client.get(project.urls["update"])
            self.assertNotContains(response, "id_flat_rate")

    def test_project_closing_reopening(self):
        """Closing a project in the future isn't allowed"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                "closed_on": in_days(10).isoformat(),
            },
        )
        self.assertContains(
            response, "Leave this empty if you do not want to close the project yet."
        )

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                "closed_on": dt.date(2019, 12, 31).isoformat(),
            },
        )
        self.assertRedirects(response, project.urls["detail"])

        project.refresh_from_db()
        self.assertEqual(
            project.status_badge,
            '<span class="badge badge-light">Order, closed on 31.12.2019</span>',
        )

    def test_initialize_customer_contact(self):
        """Initialize customer and/or contact using query parameters"""
        person = factories.PersonFactory(
            organization=factories.OrganizationFactory.create()
        )

        self.client.force_login(person.primary_contact)

        self.assertEqual(
            self.client.get(Project.urls["create"] + "?customer=0").status_code, 200
        )
        self.assertEqual(
            self.client.get(Project.urls["create"] + "?contact=0").status_code, 200
        )

        response = self.client.get(
            Project.urls["create"] + "?customer={}".format(person.organization_id)
        )
        self.assertContains(response, 'value="{}"'.format(person.organization))
        self.assertNotContains(response, 'value="{}"'.format(person))

        response = self.client.get(
            Project.urls["create"] + "?contact={}".format(person.id)
        )
        self.assertContains(response, 'value="{}"'.format(person.organization))
        self.assertContains(response, 'value="{}"'.format(person))

    def test_unspecific_service_title(self):
        """Unspecific titles raise a warning"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Programmierung allgemein",
                "effort_type": "Consulting",
                "effort_rate": "180",
                "allow_logging": True,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "unspecific-service")

        response = self.client.post(
            project.urls["createhours"],
            {
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-hours": "0.1",
                "modal-description": "Test",
                "modal-service_title": "Programmierung allgemein",
                "modal-service_description": "service description",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "unspecific-service")
