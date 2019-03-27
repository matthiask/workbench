from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from workbench import factories
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.tools.formats import local_date_format
from workbench.tools.forms import WarningsForm
from workbench.tools.testing import messages


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

        response = send(service="")
        self.assertContains(
            response,
            "Dieses Feld wird benötigt, ausser Du erstellst eine neue Leistung.",
        )

        project.closed_on = date.today()
        project.save()

        response = send()
        self.assertContains(response, "Dieses Projekt wurde schon geschlossen.")

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

        response = self.client.get(
            entry.urls["detail"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            '<a href="/projects/{}/">service title - service description'
            "</a>".format(project.id),
        )

    def test_create_and_update_logged_cost(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        response = self.client.post(
            project.urls["createcost"],
            {
                "rendered_on": local_date_format(date.today()),
                "cost": "10",
                "third_party_costs": "9",
                "description": "Anything",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        cost = LoggedCost.objects.get()
        project.closed_on = date.today()
        project.save()

        response = self.client.post(
            cost.urls["update"],
            {
                "rendered_on": local_date_format(date.today()),
                "cost": "10",
                "third_party_costs": "9",
                "description": "Anything",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "Dieses Projekt wurde schon geschlossen.")

        response = self.client.post(
            cost.urls["update"],
            {
                "rendered_on": local_date_format(date.today()),
                "cost": "10",
                "third_party_costs": "9",
                "description": "Anything",
                WarningsForm.ignore_warnings_id: "on",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 202)

    def test_update_old_disabled_fields(self):
        hours = factories.LoggedHoursFactory.create(
            rendered_on=date.today() - timedelta(days=10)
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
            '<input type="text" name="rendered_on" value="{}"'
            ' class=" datepicker form-control" required disabled id="id_rendered_on">'
            "".format(local_date_format(hours.rendered_on)),
            html=True,
        )

    def test_logged_hours_deletion(self):
        hours = factories.LoggedHoursFactory.create(
            rendered_on=date.today() - timedelta(days=10)
        )
        self.client.force_login(hours.rendered_by)
        response = self.client.post(
            hours.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            messages(response), ["Kann Stunden vergangener Wochen nicht löschen."]
        )

        hours.archived_at = timezone.now()
        hours.save()

        response = self.client.post(
            hours.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            messages(response), ["Kann archivierte Stunden nicht löschen."]
        )

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
        self.assertEqual(messages(response), ["Kann archivierte Kosten nicht löschen."])

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
        valid("rendered_by=" + str(user.pk))
        valid("project=" + str(hours.service.project.pk))
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
        valid("created_by=" + str(user.pk))
        valid("project=" + str(cost.project.pk))
        valid("organization=" + str(cost.project.customer.pk))
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
            response, cost.urls["list"] + "?project=" + str(cost.project_id)
        )
        response = self.client.get(cost.urls["update"])
        self.assertRedirects(
            response, cost.urls["list"] + "?project=" + str(cost.project_id)
        )
        response = self.client.get(cost.urls["delete"])
        self.assertRedirects(
            response, cost.urls["list"] + "?project=" + str(cost.project_id)
        )

    def test_autofill_field(self):
        hours = factories.LoggedHoursFactory.create(
            created_at=timezone.now() - timedelta(hours=2)
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
