import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from freezegun import freeze_time

from workbench import factories
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import check_code, messages
from workbench.tools.validation import logbook_lock


class LogbookTest(TestCase):
    fixtures = ["exchangerates.json"]

    def test_create_logged_hours(self):
        service = factories.ServiceFactory.create()
        project = service.project
        self.client.force_login(project.owned_by)

        def send(url=project.urls["createhours"], **kwargs):
            data = {
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-service": service.id,
                "modal-hours": "0.1",
                "modal-description": "Test",
            }
            data.update({"modal-%s" % key: value for key, value in kwargs.items()})
            return self.client.post(url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

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
        self.assertContains(response, "This project has been closed recently.")

        project.closed_on = dt.date.today() - dt.timedelta(days=20)
        project.save()
        response = send()
        self.assertContains(response, "This project has been closed too long ago.")

    def test_move_to_past_week_forbidden(self):
        hours = factories.LoggedHoursFactory.create()
        self.client.force_login(hours.rendered_by)

        response = self.client.post(
            hours.urls["update"],
            {
                "modal-rendered_by": hours.rendered_by_id,
                "modal-rendered_on": (
                    dt.date.today() - dt.timedelta(days=7)
                ).isoformat(),
                "modal-service": hours.service_id,
                "modal-hours": "0.1",
                "modal-description": "Test",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(
            response, "Sorry, hours have to be logged in the same week."
        )

    def test_update_past_week_allowed(self):
        day = dt.date.today() - dt.timedelta(days=7)
        hours = factories.LoggedHoursFactory.create(rendered_on=day)
        self.client.force_login(hours.rendered_by)

        response = self.client.post(
            hours.urls["update"],
            {
                "modal-rendered_by": hours.rendered_by_id,
                "modal-rendered_on": day.isoformat(),
                "modal-service": hours.service_id,
                "modal-hours": "0.1",
                "modal-description": "Test 2",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

    def test_past_week_logging(self):
        service = factories.ServiceFactory.create()
        project = service.project
        user = factories.UserFactory.create(enforce_same_week_logging=False)

        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createhours"],
            {
                "modal-rendered_by": user.id,
                "modal-rendered_on": (
                    dt.date.today() - dt.timedelta(days=10)
                ).isoformat(),
                "modal-service": service.id,
                "modal-hours": "0.1",
                "modal-description": "Test",
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
            '<input type="number" name="modal-hours" value="0.1" step="0.1" class="form-control" required id="id_modal-hours">',  # noqa
            html=True,
        )

        user.enforce_same_week_logging = True
        user.save()

        response = self.client.get(
            entry.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            '<input type="number" name="modal-hours" value="0.1" step="0.1" class="form-control" required disabled id="id_modal-hours">',  # noqa
            html=True,
        )

    def test_log_and_create_service(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createhours"],
            {
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                # "modal-service": service.id,
                "modal-hours": "0.1",
                "modal-description": "Test",
                "modal-service_title": "service title",
                "modal-service_description": "service description",
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
            '<a href="/projects/{}/#service{}">service title - service description'
            "</a>".format(project.id, entry.service.id),
        )

    def test_log_and_create_service_with_flat_rate(self):
        project = factories.ProjectFactory.create(flat_rate=250)
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createhours"],
            {
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                # "modal-service": service.id,
                "modal-hours": "0.1",
                "modal-description": "Test",
                "modal-service_title": "service title",
                "modal-service_description": "service description",
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
                "modal-rendered_by": service.project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-service": service.id,
                "modal-hours": "0.1",
                "modal-description": "Test",
                "modal-service_title": "service title",
                "modal-service_description": "service description",
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
                "modal-rendered_by": service.project.owned_by_id,
                "modal-rendered_on": "20.14.2019",
                "modal-service": service.id,
                "modal-hours": "0.1",
                "modal-description": "Test",
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
                "modal-rendered_by": service.project.owned_by_id,
                "modal-rendered_on": "11.2313231",
                "modal-initial-rendered_on": "2019-07-11",
                "modal-service": service.id,
                "modal-hours": "0.1",
                "modal-description": "Test",
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
                "modal-service": service.id,
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-cost": "10",
                "modal-third_party_costs": "9",
                "modal-description": "Anything",
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
                "modal-service": service.id,
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-cost": "10",
                "modal-third_party_costs": "9",
                "modal-description": "Anything",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "This project has been closed recently.")

        response = self.client.post(
            cost.urls["update"],
            {
                "modal-service": service.id,
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-cost": "10",
                "modal-third_party_costs": "9",
                "modal-description": "Anything",
                WarningsForm.ignore_warnings_id: "project-closed",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

        project.closed_on = dt.date.today() - dt.timedelta(days=20)
        project.save()
        response = self.client.post(
            cost.urls["update"],
            {
                "modal-service": service.id,
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-cost": "10",
                "modal-third_party_costs": "9",
                "modal-description": "Anything",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "This project has been closed too long ago.")

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
            '<input type="number" name="modal-hours" value="1.0" step="0.1"'
            ' class="form-control" required disabled id="id_modal-hours">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="date" name="modal-rendered_on" value="{}"'
            ' class="form-control" required disabled id="id_modal-rendered_on">'
            "".format(hours.rendered_on.isoformat()),
            html=True,
        )

    @freeze_time("2019-12-15")
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

        code = check_code(self, "/logbook/hours/")
        code("")
        code("q=test")
        code("rendered_by=-1")
        code("rendered_by=" + str(user.pk))
        code("project=" + str(hours.service.project.pk))
        code("date_from=2018-01-01")
        code("date_until=2018-01-01")
        code("service=" + str(hours.service.pk))
        code("circle=0")
        code("circle=1")
        code("role=1")
        code("organization=" + str(hours.service.project.customer.pk))
        code("not_archived=1")
        code("xlsx=1")

    def test_logged_cost_list(self):
        cost = factories.LoggedCostFactory.create()
        service = factories.ServiceFactory.create()
        user = factories.UserFactory.create()
        self.client.force_login(user)

        code = check_code(self, "/logbook/costs/")
        code("")
        code("q=test")
        code("rendered_by=-1")
        code("rendered_by=" + str(user.pk))
        code("project=" + str(cost.service.project.pk))
        code("organization=" + str(cost.service.project.customer.pk))
        code("expenses=on")
        code("date_from=2018-01-01")
        code("date_until=2018-01-01")
        code("service=0")
        code("service=" + str(service.pk))
        code("not_archived=1")
        code("xlsx=1")

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
            + "?service={}&description=blub".format(service.id),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertContains(
            response, '<option value="{}" selected>Bla</option>'.format(service.id)
        )
        self.assertContains(response, 'value="2.0"')  # hours
        self.assertContains(response, "blub")

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
            {"modal-project": project.pk},
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
                "modal-service": service.id,
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-cost": "10",
                "modal-third_party_costs": "11",
                "modal-description": "Anything",
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
                "modal-service": service.id,
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-cost": "10",
                "modal-third_party_costs": "11",
                "modal-description": "Anything",
                WarningsForm.ignore_warnings_id: "third-party-costs-higher",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

    @override_settings(FEATURES={"foreign_currencies": False})
    def test_no_role(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.get(
            project.urls["createcost"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertNotContains(response, "id_modal-expense_currency")
        self.assertNotContains(response, "id_modal-expense_cost")

    @freeze_time("2019-12-31")
    def test_logbook_lock_monday(self):
        self.assertEqual(logbook_lock(), dt.date(2019, 12, 30))

    @freeze_time("2020-01-02")
    def test_logbook_lock_first_of_year(self):
        self.assertEqual(logbook_lock(), dt.date(2020, 1, 1))
