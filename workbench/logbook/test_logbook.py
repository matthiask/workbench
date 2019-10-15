import datetime as dt

from django.test import TestCase
from django.utils import timezone

from workbench import factories
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import messages


class LogbookTest(TestCase):
    def test_create_logged_hours(self):
        service = factories.ServiceFactory.create()
        project = service.project
        self.client.force_login(project.owned_by)

        def send(url=project.urls["createhours"], **kwargs):
            return self.client.post(
                url,
                {
                    "rendered_by": project.owned_by_id,
                    "rendered_on": dt.date.today().isoformat(),
                    "service": service.id,
                    "hours": "0.1",
                    "description": "Test",
                    **kwargs,
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        response = send()
        self.assertEqual(response.status_code, 201)

        hours = LoggedHours.objects.get()
        self.assertEqual(hours.description, "Test")

        response = send()
        self.assertContains(response, "This seems to be a duplicate.")

        response = send(
            rendered_on=(dt.date.today() - dt.timedelta(days=10)).isoformat()
        )
        self.assertContains(
            response, "Sorry, hours have to be logged in the same week."
        )

        response = send(
            rendered_on=(dt.date.today() + dt.timedelta(days=10)).isoformat()
        )
        self.assertContains(response, "Sorry, too early.")

        response = send(service="")
        self.assertContains(
            response, "This field is required unless you create a new service."
        )

        response = send(hours.urls["update"], description="Test 2")
        self.assertEqual(response.status_code, 202)
        hours.refresh_from_db()
        self.assertEqual(hours.description, "Test 2")

        project.closed_on = dt.date.today()
        project.save()

        response = send()
        self.assertContains(response, "This project is already closed.")

    def test_past_week_logging(self):
        service = factories.ServiceFactory.create()
        project = service.project
        user = factories.UserFactory.create(enforce_same_week_logging=False)

        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createhours"],
            {
                "rendered_by": user.id,
                "rendered_on": (dt.date.today() - dt.timedelta(days=10)).isoformat(),
                "service": service.id,
                "hours": "0.1",
                "description": "Test",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        entry = LoggedHours.objects.get()
        response = self.client.get(
            entry.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            '<input type="number" name="hours" value="0.1" step="0.1" class="form-control" required id="id_hours">',  # noqa
            html=True,
        )

        user.enforce_same_week_logging = True
        user.save()

        response = self.client.get(
            entry.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            '<input type="number" name="hours" value="0.1" step="0.1" class="form-control" required disabled id="id_hours">',  # noqa
            html=True,
        )

    def test_log_and_create_service(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createhours"],
            {
                "rendered_by": project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
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
        self.assertIsNone(entry.service.effort_rate)

        response = self.client.get(
            entry.urls["detail"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            '<a href="/projects/{}/">service title - service description'
            "</a>".format(project.id),
        )

    def test_log_and_create_service_with_flat_rate(self):
        project = factories.ProjectFactory.create(flat_rate=250)
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createhours"],
            {
                "rendered_by": project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
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
        self.assertEqual(entry.service.effort_rate, 250)

    def test_log_and_both_service_create(self):
        service = factories.ServiceFactory.create()

        self.client.force_login(service.project.owned_by)

        response = self.client.post(
            service.project.urls["createhours"],
            {
                "rendered_by": service.project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
                "service": service.id,
                "hours": "0.1",
                "description": "Test",
                "service_title": "service title",
                "service_description": "service description",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Deselect the existing service if you want to create a new service.",
        )

    def test_invalid_date(self):
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        response = self.client.post(
            service.project.urls["createhours"],
            {
                "rendered_by": service.project.owned_by_id,
                "rendered_on": "20.14.2019",
                "service": service.id,
                "hours": "0.1",
                "description": "Test",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid date.")

    def test_duplicate_detection_with_invalid_date(self):
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        factories.LoggedHoursFactory.create(
            service=service, rendered_by=service.project.owned_by
        )

        response = self.client.post(
            service.project.urls["createhours"],
            {
                "rendered_by": service.project.owned_by_id,
                "rendered_on": "11.2313231",
                "initial-rendered_on": "2019-07-11",
                "service": service.id,
                "hours": "0.1",
                "description": "Test",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid date.")

    def test_create_and_update_logged_cost(self):
        service = factories.ServiceFactory.create()
        project = service.project
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createcost"],
            {
                "service": service.id,
                "rendered_by": project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
                "cost": "10",
                "third_party_costs": "9",
                "description": "Anything",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        cost = LoggedCost.objects.get()
        project.closed_on = dt.date.today()
        project.save()

        response = self.client.post(
            cost.urls["update"],
            {
                "service": service.id,
                "rendered_by": project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
                "cost": "10",
                "third_party_costs": "9",
                "description": "Anything",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "This project is already closed.")

        response = self.client.post(
            cost.urls["update"],
            {
                "service": service.id,
                "rendered_by": project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
                "cost": "10",
                "third_party_costs": "9",
                "description": "Anything",
                WarningsForm.ignore_warnings_id: "project-closed",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

    def test_update_old_disabled_fields(self):
        hours = factories.LoggedHoursFactory.create(
            rendered_on=dt.date.today() - dt.timedelta(days=10)
        )
        self.client.force_login(hours.rendered_by)
        response = self.client.get(
            hours.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            '<input type="number" name="hours" value="1.0" step="0.1"'
            ' class="form-control" required disabled id="id_hours">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="date" name="rendered_on" value="{}"'
            ' class="form-control" required disabled id="id_rendered_on">'
            "".format(hours.rendered_on.isoformat()),
            html=True,
        )

    def test_logged_hours_deletion(self):
        hours = factories.LoggedHoursFactory.create(
            rendered_on=dt.date.today() - dt.timedelta(days=10)
        )
        self.client.force_login(hours.rendered_by)
        response = self.client.post(
            hours.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            messages(response), ["Cannot delete logged hours from past weeks."]
        )

        hours.archived_at = timezone.now()
        hours.save()

        response = self.client.post(
            hours.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(messages(response), ["Cannot delete archived logged hours."])

        hours = factories.LoggedHoursFactory.create()
        response = self.client.post(
            hours.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 204)

    def test_logged_cost_deletion(self):
        costs = factories.LoggedCostFactory.create(archived_at=timezone.now())
        self.client.force_login(costs.created_by)

        response = self.client.post(
            costs.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            messages(response), ["Cannot delete archived logged cost entries."]
        )

        costs = factories.LoggedCostFactory.create()
        response = self.client.post(
            costs.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 204)

    def test_logged_hours_list(self):
        factories.LoggedHoursFactory.create()
        hours = factories.LoggedHoursFactory.create()
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def valid(p):
            self.assertEqual(self.client.get("/logbook/hours/?" + p).status_code, 200)

        valid("")
        valid("q=test")
        valid("rendered_by=" + str(user.pk))
        valid("project=" + str(hours.service.project.pk))
        valid("until=2018-01-01")
        valid("service=" + str(hours.service.pk))
        valid("organization=" + str(hours.service.project.customer.pk))
        valid("xlsx=1")

    def test_logged_cost_list(self):
        cost = factories.LoggedCostFactory.create()
        service = factories.ServiceFactory.create()
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def valid(p):
            self.assertEqual(self.client.get("/logbook/costs/?" + p).status_code, 200)

        valid("")
        valid("q=test")
        valid("rendered_by=" + str(user.pk))
        valid("project=" + str(cost.service.project.pk))
        valid("organization=" + str(cost.service.project.customer.pk))
        valid("expenses=on")
        valid("until=2018-01-01")
        valid("service=0")
        valid("service=" + str(service.pk))
        valid("xlsx=1")

    def test_non_ajax_redirect_hours(self):
        hours = factories.LoggedHoursFactory.create()
        self.client.force_login(hours.rendered_by)
        response = self.client.get(hours.urls["detail"])
        self.assertRedirects(
            response, hours.urls["list"] + "?project=" + str(hours.service.project_id)
        )

    def test_non_ajax_redirect_cost(self):
        cost = factories.LoggedCostFactory.create()
        self.client.force_login(cost.created_by)
        response = self.client.get(cost.urls["detail"])
        self.assertRedirects(
            response, cost.urls["list"] + "?project=" + str(cost.service.project_id)
        )
        response = self.client.get(cost.urls["update"])
        self.assertRedirects(
            response, cost.urls["list"] + "?project=" + str(cost.service.project_id)
        )
        response = self.client.get(cost.urls["delete"])
        self.assertRedirects(
            response, cost.urls["list"] + "?project=" + str(cost.service.project_id)
        )

    def test_autofill_field(self):
        hours = factories.LoggedHoursFactory.create(
            created_at=timezone.now() - dt.timedelta(hours=2)
        )
        self.client.force_login(hours.rendered_by)

        response = self.client.get(
            hours.service.project.urls["createhours"],
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(
            response,
            '<option value="{}" selected>Any service</option>'.format(hours.service_id),
        )
        self.assertContains(response, 'value="2.0"')  # hours

        service = factories.ServiceFactory.create(
            project=hours.service.project, title="Bla"
        )
        response = self.client.get(
            hours.service.project.urls["createhours"]
            + "?service={}".format(service.id),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertContains(
            response, '<option value="{}" selected>Bla</option>'.format(service.id)
        )
        self.assertContains(response, 'value="2.0"')  # hours

    def test_redirect(self):
        self.client.force_login(factories.UserFactory.create())
        self.assertRedirects(self.client.get("/logbook/"), "/logbook/hours/")

    def test_initialize_hours(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        response = self.client.get(
            project.urls["createhours"] + "?hours=1.5",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, 'value="1.5"')

    def test_copy(self):
        hours = factories.LoggedHoursFactory.create()
        self.client.force_login(factories.UserFactory.create())

        response = self.client.get(
            hours.service.project.urls["createhours"] + "?copy=" + str(hours.pk),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, " selected>Any service</option>")

        response = self.client.get(
            hours.service.project.urls["createhours"] + "?copy=bla",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)  # No crash

    def test_pre_form(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get("/logbook/hours/create/")
        self.assertRedirects(response, "/")

        response = self.client.get(
            "/logbook/hours/create/", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response, 'data-autocomplete-url="/projects/autocomplete/?only_open=on"'
        )

        response = self.client.post(
            "/logbook/hours/create/",
            {"project-project": project.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        # Do not fetch the redirect response because the X-Requested-With
        # header value will be missing on the second request.
        self.assertRedirects(
            response, project.urls["createhours"], fetch_redirect_response=False
        )

    def test_cost_gte_third_party_costs(self):
        service = factories.ServiceFactory.create()
        project = service.project
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createcost"],
            {
                "service": service.id,
                "rendered_by": project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
                "cost": "10",
                "third_party_costs": "11",
                "description": "Anything",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Third party costs shouldn&#x27;t be higher than costs."
        )

        response = self.client.post(
            project.urls["createcost"],
            {
                "service": service.id,
                "rendered_by": project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
                "cost": "10",
                "third_party_costs": "11",
                "description": "Anything",
                WarningsForm.ignore_warnings_id: "third-party-costs-higher",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)
