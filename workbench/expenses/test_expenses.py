import datetime as dt

from django.test import TestCase
from django.utils import timezone

from workbench import factories
from workbench.expenses.models import ExpenseReport
from workbench.logbook.models import LoggedCost
from workbench.tools.formats import local_date_format
from workbench.tools.testing import messages


class ExpensesTest(TestCase):
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

    def test_list(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        report = ExpenseReport.objects.create(created_by=user, owned_by=user)
        report.expenses.set(
            [
                factories.LoggedCostFactory.create(
                    rendered_by=user, are_expenses=True, third_party_costs=5
                )
            ]
        )

        def valid(p):
            self.assertEqual(self.client.get("/expenses/?" + p).status_code, 200)

        valid("")
        valid("q=test")

    def test_expenses(self):
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        service = factories.ServiceFactory.create(project=project)

        response = self.client.post(
            project.urls["createcost"],
            {
                "service": service.id,
                "rendered_by": project.owned_by_id,
                "rendered_on": local_date_format(dt.date.today()),
                "cost": "10",
                "description": "Anything",
                "are_expenses": "on",
                # "third_party_costs": "9",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(
            response, "Providing third party costs is necessary for expenses."
        )

        response = self.client.post(
            project.urls["createcost"],
            {
                "service": service.id,
                "rendered_by": project.owned_by_id,
                "rendered_on": dt.date.today().isoformat(),
                "cost": "10",
                "description": "Anything",
                "are_expenses": "on",
                "third_party_costs": "9",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)

        cost1 = LoggedCost.objects.get()
        self.assertEqual(
            list(LoggedCost.objects.expenses(user=project.owned_by)), [cost1]
        )

        # Another users' expenses
        factories.LoggedCostFactory.create(are_expenses=True, third_party_costs=5)

        response = self.client.get("/expenses/create/")
        # Only one expense
        self.assertContains(response, "id_expenses_0")
        self.assertNotContains(response, "id_expenses_1")

        response = self.client.post("/expenses/create/", {"expenses": [cost1.pk]})
        report = ExpenseReport.objects.get()
        self.assertRedirects(response, report.urls["detail"])
        self.assertEqual(report.total, 9)

        self.assertEqual(self.client.get(report.urls["pdf"]).status_code, 200)

        # Some fields are now disabled
        response = self.client.get(
            cost1.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            '<input type="number" name="third_party_costs" value="9.00" step="0.01" class="form-control" disabled id="id_third_party_costs">',  # noqa
            html=True,
        )

        response = self.client.get(
            cost1.urls["delete"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response, "Expenses are part of an expense report, cannot delete entry."
        )

        # More expenses of same user
        cost2 = factories.LoggedCostFactory.create(
            rendered_by=project.owned_by, are_expenses=True, third_party_costs=5
        )
        response = self.client.post(report.urls["update"], {"expenses": [cost2.pk]})
        self.assertRedirects(response, report.urls["detail"])
        report.refresh_from_db()
        self.assertEqual(report.total, 5)

        response = self.client.post(report.urls["delete"])
        self.assertRedirects(response, "/expenses/")

        self.assertEqual(ExpenseReport.objects.count(), 0)

        response = self.client.post(
            "/expenses/create/", {"expenses": [cost1.pk], "is_closed": "on"}
        )
        report = ExpenseReport.objects.get()
        self.assertRedirects(response, report.urls["detail"])
        self.assertEqual(report.total, 9)

        response = self.client.post(report.urls["update"])
        self.assertRedirects(response, report.urls["detail"])
        self.assertEqual(messages(response), ["Cannot update a closed expense report."])

        response = self.client.post(report.urls["delete"])
        self.assertRedirects(response, report.urls["detail"])
        self.assertEqual(messages(response), ["Cannot delete a closed expense report."])
        # print(response, response.content.decode("utf-8"))
