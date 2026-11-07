import datetime as dt

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.contacts.models import Organization
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedHours
from workbench.offers.models import Offer
from workbench.projects.charts import projected_vs_invoiced_chart
from workbench.projects.models import InternalType, Project, Service
from workbench.projects.views import projected_invoices_timeline
from workbench.tools.formats import local_date_format
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code, messages
from workbench.tools.validation import in_days


class ProjectsTest(TestCase):
    @override_settings(FEATURES={"INTERNAL_TYPES": F.NEVER})
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
        self.assertEqual(response.status_code, 302)
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
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Production service",
                "effort_type": "Production",
                # "effort_rate": "180",
                "allow_logging": True,
            },
            headers={"x-requested-with": "XMLHttpRequest"},
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
            },
            headers={"x-requested-with": "XMLHttpRequest"},
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
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 201)

        service1, service2 = project.services.all()

        service1.loggedcosts.create(created_by=user, rendered_by=user, cost=10)

        response = self.client.post(
            Service.urls["set_order"], {"ids": [service2.id, service1.id]}
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(list(project.services.all()), [service2, service1])

        self.assertRedirects(
            self.client.get(service1.urls["detail"]),
            "{}#service{}".format(project.urls["detail"], service1.pk),
        )
        response = self.client.post(
            service1.urls["update"],
            {
                "title": "Production service",
                "effort_type": "Consulting",
                "effort_rate": "200",
                "effort_hours": 20,
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)
        service1.refresh_from_db()
        self.assertAlmostEqual(service1.service_cost, 4000)

        response = self.client.post(
            service1.urls["delete"], headers={"x-requested-with": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(project.services.all()), {service1, service2})

        self.assertEqual(service1.loggedcosts.count(), 1)
        self.assertEqual(service2.loggedcosts.count(), 0)
        response = self.client.post(
            service1.urls["reassign_logbook"],
            {"service": service2.pk},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)

        self.assertEqual(service1.loggedcosts.count(), 0)
        self.assertEqual(service2.loggedcosts.count(), 1)

        response = self.client.post(
            service1.urls["reassign_logbook"],
            {"service": service2.pk, "try_delete": "on"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(set(project.services.all()), {service2})

    def test_reassign_include_invoiced(self):
        """Reassigning logbook entries leaves invoiced entries where they are
        unless they are included, the option is only offered if there are any"""
        project = factories.ProjectFactory.create()
        service = factories.ServiceFactory.create(project=project)
        target = factories.ServiceFactory.create(project=project)
        factories.LoggedHoursFactory.create(service=service, hours=3)
        factories.LoggedCostFactory.create(service=service, cost=100)
        self.client.force_login(project.owned_by)
        url = service.urls["reassign_logbook"]
        ajax = {"x-requested-with": "XMLHttpRequest"}

        self.assertNotContains(self.client.get(url, headers=ajax), "include_invoiced")

        invoice = factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_logbook([service])
        open_hours = factories.LoggedHoursFactory.create(service=service, hours=2)
        open_cost = factories.LoggedCostFactory.create(service=service, cost=50)
        self.assertContains(self.client.get(url, headers=ajax), "include_invoiced")

        response = self.client.post(url, {"service": target.pk}, headers=ajax)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(list(target.loggedhours.all()), [open_hours])
        self.assertEqual(list(target.loggedcosts.all()), [open_cost])
        self.assertEqual(service.loggedhours.count(), 1)
        self.assertEqual(service.loggedcosts.count(), 1)

        response = self.client.post(
            url, {"service": target.pk, "include_invoiced": "on"}, headers=ajax
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(service.loggedhours.count(), 0)
        self.assertEqual(service.loggedcosts.count(), 0)

    def test_try_delete_available(self):
        """The try_delete box is only available if service isn't bound to an offer"""
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        response = self.client.get(
            service.urls["reassign_logbook"],
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, "try_delete")
        offer = factories.OfferFactory.create(
            project=service.project, status=Offer.ACCEPTED
        )
        service.offer = offer
        service.save()
        response = self.client.get(
            service.urls["reassign_logbook"],
            headers={"x-requested-with": "XMLHttpRequest"},
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

    def test_service_effort_type_on_project(self):
        """The project page shows the effort type of services"""
        service = factories.ServiceFactory.create(
            effort_type="Projektleitung", effort_rate=180, effort_hours=8
        )
        self.client.force_login(service.project.owned_by)
        response = self.client.get(service.project.get_absolute_url())
        self.assertContains(
            response, '<span class="wb-figure-note">Projektleitung</span>'
        )

    def test_service_hours_without_rate(self):
        """Optional services don't count towards the budgeted hours without
        an effort rate, like towards all other budgeted totals"""
        project = factories.ProjectFactory.create()
        factories.ServiceFactory.create(project=project, effort_hours=5)
        factories.ServiceFactory.create(
            project=project, effort_hours=3, is_optional=True
        )

        gs = project.grouped_services
        self.assertEqual(gs["total_service_hours_rate_undefined"], 5)

    def test_clearable_date_fields(self):
        """Optional date fields can be cleared with a button"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        response = self.client.get(project.urls["update"])
        self.assertContains(response, 'data-clear="#id_closed_on"')

        absence = project.owned_by.absences.create(
            starts_on=dt.date.today(), days=1, reason="vacation"
        )
        response = self.client.get(
            absence.urls["update"], headers={"x-requested-with": "XMLHttpRequest"}
        )
        self.assertContains(response, 'data-clear="#id_modal-ends_on"')
        self.assertNotContains(response, 'data-clear="#id_modal-starts_on"')

    def test_autofill(self):
        """Required autofilling attributes for service types are available"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(
            project.urls["createservice"],
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, 'data-autofill="{}"')

        factories.service_types()

        response = self.client.get(
            project.urls["createservice"],
            headers={"x-requested-with": "XMLHttpRequest"},
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
                    (
                        "The contact Vorname Nachname"
                        " does not belong to The Organization Ltd."
                    )
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
        code("s=no-projected-gross-margin")
        code("s=empty-logbook")
        code("s=invalid-customer-contact-combination")
        code(f"org={project.customer_id}")
        code("type=internal")
        code("type=maintenance")
        code(f"owned_by={user.id}")
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
        self.assertContains(response, f'value="{project.title}"')
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
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, "This project is already closed.")

        response = self.client.post(
            service.urls["move"],
            {"modal-project": flat_rate.pk},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, 'value="new-project-has-flat-rate"')

        response = self.client.post(
            service.urls["move"],
            {"modal-project": project.pk},
            headers={"x-requested-with": "XMLHttpRequest"},
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
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)

        service.refresh_from_db()
        self.assertEqual(service.effort_rate, 100)

    def test_move_service_bound_to_offer(self):
        """Moving a service bound to an offer should fail"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        service = factories.ServiceFactory.create(project=project, offer=offer)

        other = factories.ProjectFactory.create()

        self.client.force_login(project.owned_by)
        response = self.client.get(
            service.urls["move"], headers={"x-requested-with": "XMLHttpRequest"}
        )
        self.assertContains(
            response, "Cannot move a service which is already bound to an offer."
        )

        response = self.client.post(
            service.urls["move"],
            {"modal-project": other.pk},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(
            response, "The offer must belong to the same project as the service."
        )

    def test_move_service_with_invoiced_entries(self):
        """Services whose logged hours or costs have been invoiced stay with
        the project of the invoice"""
        service = factories.ServiceFactory.create()
        other = factories.ProjectFactory.create()
        hours = factories.LoggedHoursFactory.create(service=service)
        self.client.force_login(service.project.owned_by)

        LoggedHours.objects.filter(pk=hours.pk).update(archived_at=timezone.now())
        response = self.client.post(
            service.urls["move"],
            {"modal-project": other.pk},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(
            response,
            "Logged hours or costs of this service have been invoiced already,"
            " it cannot be moved to another project.",
        )
        service.refresh_from_db()
        self.assertNotEqual(service.project, other)

    def test_external_reference_of_service_bound_to_offer(self):
        """The external reference of services stays editable when their offer
        has been sent or accepted, the other fields don't"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        service = factories.ServiceFactory.create(
            project=project, offer=offer, title="Design"
        )
        Offer.objects.filter(pk=offer.pk).update(status=Offer.ACCEPTED)

        self.client.force_login(project.owned_by)
        response = self.client.post(
            service.urls["update"],
            {
                "title": "Something else",
                "external_reference": "https://example.com/issues/1",
                "allow_logging": True,
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)
        service.refresh_from_db()
        self.assertEqual(service.external_reference, "https://example.com/issues/1")
        self.assertEqual(service.title, "Design")

    def test_select(self):
        """Test the project select modal"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["select"])
        self.assertRedirects(response, "/")

        response = self.client.get(
            project.urls["select"], headers={"x-requested-with": "XMLHttpRequest"}
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
            headers={"x-requested-with": "XMLHttpRequest"},
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

    def test_long_service_descriptions_in_choices(self):
        """Long descriptions aren't truncated, the combobox wraps them"""
        service = factories.ServiceFactory.create(
            title="Projektleitung", description="Lorem ipsum " * 100
        )
        self.client.force_login(service.project.owned_by)

        response = self.client.get(service.project.urls["services"])
        label = response.json()["services"][0]["options"][0]["label"]
        self.assertEqual(label, str(service))

        response = self.client.get(
            service.project.urls["createhours"],
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, "data-combobox")
        self.assertContains(response, str(service).strip())

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
            + f"?service_type={service_types.consulting.pk}"
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
            headers={"x-requested-with": "XMLHttpRequest", "accept-language": "en"},
        )
        # print(response.content.decode("utf-8"))

        self.assertContains(
            response,
            '<input type="number" name="effort_rate" value="250.00" step="0.01" class="form-control" disabled id="id_effort_rate">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="text" name="effort_type" value="Pauschalsatz" maxlength="50" class="form-control" disabled id="id_effort_type">',
            html=True,
        )
        self.assertNotContains(response, 'id="id_service_type"')
        # The autofill script expects the service type select
        self.assertNotContains(response, "data-autofill")

    def test_add_flat_rate_to_existing_project(self):
        """Adding a flat rate to a project with services warns about
        overridding their effort rate"""
        service = factories.ServiceFactory.create(
            effort_type="Hello",
            effort_rate=200,
            effort_hours=1,
        )
        self.assertEqual(service.service_cost, 200)

        project = service.project
        # Services of service groups can still be changed, those of offers
        # which have been sent can't
        grouped, sent = [
            factories.ServiceFactory.create(
                project=project,
                offer=factories.OfferFactory.create(
                    project=project,
                    status=status,
                    offered_on=in_days(0),
                    valid_until=in_days(30),
                ),
                effort_type="Hello",
                effort_rate=200,
                effort_hours=1,
            )
            for status in [Offer.SERVICE_GROUP, Offer.OFFERED]
        ]
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

        service.refresh_from_db()
        self.assertEqual(service.effort_rate, 250)
        self.assertEqual(service.effort_type, "Pauschalsatz")
        self.assertEqual(service.service_cost, 250)
        grouped.refresh_from_db()
        self.assertEqual(grouped.effort_rate, 250)
        sent.refresh_from_db()
        self.assertEqual(sent.effort_rate, 200)

    def test_no_flat_rate(self):
        """Uses without CONTROLLING do not see the flat rate field"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(project.urls["update"])
        self.assertContains(response, "id_flat_rate")

        with override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER}):
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
            '<span class="badge wb-project-type wb-project-type--order'
            ' wb-project-type--closed">Order, closed on 31.12.2019</span>',
        )

    def test_status_badge(self):
        """The badge shows the type, internal outreach projects get their own"""
        outreach = InternalType.objects.create(
            name="Outreach", percentage=10, is_outreach=True
        )
        other = InternalType.objects.create(name="Other", percentage=10)
        cases = [
            ({"type": Project.ORDER}, "order", "Order"),
            ({"type": Project.MAINTENANCE}, "maintenance", "Maintenance"),
            (
                {"type": Project.INTERNAL, "internal_type": other},
                "internal",
                "Internal",
            ),
            (
                {"type": Project.INTERNAL, "internal_type": outreach},
                "outreach",
                "Internal · Outreach",
            ),
        ]
        for kwargs, kind, label in cases:
            with self.subTest(kind=kind):
                project = factories.ProjectFactory.create(**kwargs)
                project = Project.objects.get(pk=project.pk)
                self.assertEqual(
                    project.status_badge,
                    f'<span class="badge wb-project-type wb-project-type--{kind}">'
                    f"{label}</span>",
                )

        # The internal type isn't loaded for the badge
        projects = list(Project.objects.all())
        with self.assertNumQueries(0):
            for project in projects:
                str(project.status_badge)

        # Changing internal types takes effect right away
        other.is_outreach = True
        other.save()
        project = Project.objects.get(internal_type=other)
        self.assertIn("wb-project-type--outreach", project.status_badge)

    def test_closing_discards_offers_in_preparation(self):
        """Offers in preparation of closed projects are discarded, they can't
        lead anywhere anymore, or declined if they have been sent before;
        offers which have been sent are left alone"""
        project = factories.ProjectFactory.create()
        preparing = factories.OfferFactory.create(project=project)
        revised = factories.OfferFactory.create(
            project=project,
            offered_on=in_days(-30),
            valid_until=None,
            title="Revised",
            postal_address="A\nStreet\nCity",
        )
        offered = factories.OfferFactory.create(
            project=project,
            status=Offer.OFFERED,
            offered_on=in_days(-10),
            valid_until=in_days(20),
        )
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.type,
                "closed_on": in_days(-1).isoformat(),
            },
        )
        self.assertRedirects(response, project.urls["detail"])
        self.assertIn(
            f"Offers in preparation have been discarded: {preparing}.",
            messages(response),
        )

        preparing.refresh_from_db()
        offered.refresh_from_db()
        self.assertEqual(preparing.status, Offer.DISCARDED)
        self.assertEqual(preparing.closed_on, in_days(-1))
        self.assertEqual(
            preparing.pretty_status,
            f"Discarded on {local_date_format(in_days(-1))}",
        )
        self.assertEqual(offered.status, Offer.OFFERED)
        # Discarded offers don't count, like declined ones
        self.assertTrue(preparing.is_declined)

        revised.refresh_from_db()
        self.assertEqual(revised.status, Offer.DECLINED)
        self.assertEqual(revised.valid_until, in_days(-1))
        revised.full_clean()
        self.assertIn(
            f"Offers in preparation which have been sent before have been declined: {revised}.",
            messages(response),
        )

    def test_closing_with_planned_work_of_offers_in_preparation(self):
        """Closing a project discards its offers in preparation, the planned
        work of those offers needs a decision"""
        project = factories.ProjectFactory.create()
        preparing = factories.OfferFactory.create(project=project)
        factories.PlannedWorkFactory.create(
            project=project, offer=preparing, weeks=[in_days(7)]
        )
        # Planned work without offer is left alone
        factories.PlannedWorkFactory.create(project=project, weeks=[in_days(7)])
        self.client.force_login(project.owned_by)
        data = {
            "customer": project.customer_id,
            "contact": project.contact_id,
            "title": project.title,
            "owned_by": project.owned_by_id,
            "type": project.type,
            "closed_on": in_days(-1).isoformat(),
        }

        response = self.client.post(project.urls["update"], data)
        self.assertContains(
            response,
            "Please decide whether the linked planning entries should be deleted.",
        )
        project.refresh_from_db()
        self.assertIsNone(project.closed_on)

        # Editing the project without closing it doesn't ask
        response = self.client.post(
            project.urls["update"], {**data, "closed_on": "", "title": "Changed"}
        )
        self.assertRedirects(response, project.urls["detail"])

        response = self.client.post(
            project.urls["update"], {**data, "delete_planned_work": "1"}
        )
        self.assertRedirects(response, project.urls["detail"])
        preparing.refresh_from_db()
        self.assertEqual(preparing.status, Offer.DISCARDED)
        self.assertEqual(preparing.planned_work.count(), 0)
        self.assertEqual(project.planned_work.count(), 1)

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
            Project.urls["create"] + f"?customer={person.organization_id}"
        )
        self.assertContains(response, f'value="{person.organization}"')
        self.assertNotContains(response, f'value="{person}"')

        response = self.client.get(Project.urls["create"] + f"?contact={person.id}")
        self.assertContains(response, f'value="{person.organization}"')
        self.assertContains(response, f'value="{person}"')

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
            headers={"x-requested-with": "XMLHttpRequest"},
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
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, "unspecific-service")

    def test_service_description_only_url(self):
        """A description containing only a URL raises a warning"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createservice"],
            {
                "title": "Specific service title",
                "description": "https://example.com/some/reference",
                "effort_type": "Consulting",
                "effort_rate": "180",
                "allow_logging": True,
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, "description-only-url")

    def test_offer_project_mismatch(self):
        """Services with offers must not have differing projects"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create()

        msg = [("offer", ["The offer must belong to the same project as the service."])]
        with self.assertRaises(ValidationError) as cm:
            Service(project=project, offer=offer, title="Test").full_clean()
        self.assertEqual(list(cm.exception), msg)

    @override_settings(FEATURES={"INTERNAL_TYPES": F.ALWAYS})
    def test_internal_type_selecting(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        it = InternalType.objects.create(percentage=10)
        itu = it.internaltypeuser_set.create(user=project.owned_by)
        self.assertEqual(itu.percentage, 10)

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.INTERNAL,
            },
        )
        self.assertContains(response, "Selecting an internal type is required")

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.INTERNAL,
                "internal_type": it.id,
            },
        )
        self.assertRedirects(response, project.urls["detail"])

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.MAINTENANCE,
                "internal_type": it.id,
            },
        )
        self.assertContains(
            response, "The internal type must not be set when project is not internal."
        )

        response = self.client.post(
            project.urls["update"],
            {
                "customer": project.customer_id,
                "contact": project.contact_id,
                "title": project.title,
                "owned_by": project.owned_by_id,
                "type": project.MAINTENANCE,
            },
        )
        self.assertRedirects(response, project.urls["detail"])


class ProjectedInvoicesTimelineTest(TestCase):
    def test_timeline(self):
        """Projected invoices around today are listed one by one, earlier ones
        are summed up and later ones are summed up per quarter"""
        project = factories.ProjectFactory.create()
        for day, gross_margin in [
            ("2026-06-30", 100),
            ("2026-08-31", 200),
            ("2026-09-30", 300),  # Last month: shown
            ("2026-10-15", 400),
            ("2026-12-31", 500),
            ("2027-01-31", 600),  # Later: per quarter
            ("2027-03-31", 700),
            ("2027-04-30", 800),
        ]:
            factories.ProjectedInvoiceFactory.create(
                project=project,
                invoiced_on=dt.date.fromisoformat(day),
                gross_margin=gross_margin,
            )

        rows = projected_invoices_timeline(
            project.projected_invoices.all(), today=dt.date(2026, 10, 30)
        )
        self.assertEqual(
            [(row["label"], row["gross_margin"], row["count"]) for row in rows],
            [
                ("until 31.08.2026", 300, 2),
                ("30.09.2026", 300, 1),
                ("15.10.2026", 400, 1),
                ("31.12.2026", 500, 1),
                ("Q1 2027", 1300, 2),
                ("Q2 2027", 800, 1),
            ],
        )

    def test_projected_vs_invoiced(self):
        """The chart compares cumulative projected and invoiced gross margin"""
        project = factories.ProjectFactory.create()
        for day, gross_margin in [("2026-01-31", 1000), ("2026-03-31", 500)]:
            factories.ProjectedInvoiceFactory.create(
                project=project,
                invoiced_on=dt.date.fromisoformat(day),
                gross_margin=gross_margin,
            )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            invoiced_on=dt.date(2026, 2, 10),
            subtotal=1200,
            third_party_costs=200,
            status=Invoice.SENT,
        )
        factories.InvoiceFactory.create(
            project=project,
            customer=project.customer,
            contact=project.contact,
            invoiced_on=dt.date(2026, 2, 20),
            subtotal=999,
            status=Invoice.IN_PREPARATION,
        )

        chart = projected_vs_invoiced_chart(project, today=dt.date(2026, 4, 15))
        self.assertEqual(
            [point["total"] for point in chart["projected"]["points"]], [1000, 1500]
        )
        self.assertEqual(
            [point["total"] for point in chart["invoiced"]["points"]], [1000]
        )
        self.assertTrue(chart["projected"]["path"].startswith("M"))

        self.client.force_login(project.owned_by)
        response = self.client.get(
            project.urls["projected_invoices_list"],
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, "<svg")
