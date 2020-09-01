import datetime as dt
import json
import os
from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from workbench import factories
from workbench.expenses.models import ExchangeRates, ExpenseReport
from workbench.expenses.rates import exchange_rates
from workbench.logbook.models import LoggedCost
from workbench.tools.formats import local_date_format
from workbench.tools.testing import check_code, messages
from workbench.tools.validation import in_days


class ExpensesTest(TestCase):
    fixtures = ["exchangerates.json"]

    def test_logged_cost_deletion(self):
        """Archived logged costs cannot be deleted, others can"""
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
        """Filter form smoke test"""
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

        code = check_code(self, "/expenses/")
        code("")
        code("s=in-preparation")
        code("s=closed")
        code("owned_by={}".format(user.id))
        code("owned_by=-1")  # mine
        code("owned_by=0")  # only inactive

    def test_expenses(self):
        """Expense logging and expense report creation"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)

        service = factories.ServiceFactory.create(project=project)

        response = self.client.post(
            project.urls["createcost"],
            {
                "modal-service": service.id,
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": local_date_format(dt.date.today()),
                "modal-cost": "10",
                "modal-description": "Anything",
                "modal-are_expenses": "on",
                # "modal-third_party_costs": "9",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(
            response, "Providing third party costs is necessary for expenses."
        )

        response = self.client.post(
            project.urls["createcost"],
            {
                "modal-service": service.id,
                "modal-rendered_by": project.owned_by_id,
                "modal-rendered_on": dt.date.today().isoformat(),
                "modal-cost": "10",
                "modal-description": "Anything",
                "modal-are_expenses": "on",
                "modal-third_party_costs": "9",
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

        # Some fields are now disabled
        response = self.client.get(
            cost1.urls["update"], HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(
            response,
            '<input type="number" name="modal-third_party_costs" value="9.00" step="0.01" class="form-control" disabled id="id_modal-third_party_costs">',  # noqa
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

        response = self.client.get(report.urls["pdf"])
        self.assertRedirects(response, report.urls["detail"])
        self.assertEqual(
            messages(response),
            [
                "Please close the expense report first. Generating PDFs"
                " for open expense reports isn't allowed."
            ],
        )

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

        self.assertEqual(self.client.get(report.urls["pdf"]).status_code, 200)

    def test_no_expenses(self):
        """Expense report creation without expenses fails early"""
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/expenses/create/")
        self.assertRedirects(response, "/expenses/")
        self.assertEqual(
            messages(response), ["Could not find any expenses to reimburse."]
        )

    def test_exchange_rate_str(self):
        """__str__ method of exchange rates..."""
        today = dt.date.today()
        self.assertEqual(str(ExchangeRates(day=today)), str(today))

    def test_exchange_rate_conversion(self):
        """The exchange rate conversion API returns expected values"""
        # From https://api.exchangeratesapi.io/latest?base=CHF, but pruned
        ExchangeRates.objects.create(
            day=dt.date(2019, 12, 11),
            rates={
                "rates": {
                    "CHF": 1.0,
                    "EUR": 0.9160864786,
                    "USD": 1.014565775,
                    "PLN": 3.927171125,
                },
                "base": "CHF",
                "date": "2019-12-11",
            },
        )

        self.client.force_login(factories.UserFactory.create())

        response = self.client.get("/expenses/convert/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"cost": ""})

        response = self.client.get(
            "/expenses/convert/?day=2019-12-11&currency=EUR&cost=100"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"cost": "109.16"})

    def test_one_or_other(self):
        """Foreign expenses require both the expense amount and the currency"""
        service = factories.ServiceFactory.create()
        kw = {
            "service": service,
            "created_by": service.project.owned_by,
            "rendered_by": service.project.owned_by,
            "cost": 10,
            "description": "Test",
        }
        with self.assertRaises(ValidationError) as cm:
            LoggedCost(**kw, expense_currency="EUR").full_clean()
        self.assertEqual(
            list(cm.exception),
            [("expense_cost", ["Either fill in all fields or none."])],
        )

        with self.assertRaises(ValidationError) as cm:
            LoggedCost(**kw, expense_cost=10).full_clean()
        self.assertEqual(
            list(cm.exception),
            [("expense_currency", ["Either fill in all fields or none."])],
        )


def mocked_json(*args, **kwargs):
    with open(
        os.path.join(settings.BASE_DIR, "workbench", "fixtures", "exchangerates.json")
    ) as f:
        return json.load(f)[0]["fields"]["rates"]


@mock.patch("workbench.expenses.models.exchange_rates", side_effect=mocked_json)
class MockedRemoteDataTest(TestCase):
    def test_with_mocked_remote_data(self, mock_get):
        """Exchange rates determination"""
        self.assertEqual(mock_get.call_count, 0)
        rates = ExchangeRates.objects.newest()
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(rates.rates["date"], "2019-12-10")

        rates = ExchangeRates.objects.create(day=in_days(1), rates={})
        self.assertEqual(ExchangeRates.objects.newest(), rates)
        self.assertEqual(mock_get.call_count, 1)


def mocked_get(*args, **kwargs):
    class MockRequest:
        def json(self):
            return {}

    return MockRequest()


@mock.patch("workbench.expenses.rates.requests.get", side_effect=mocked_get)
class ExchangeRatesTest(TestCase):
    def test_exchange_rates_today(self, mock_get):
        """exchange_rates() without arguments fetches today's exchange rates"""
        exchange_rates()
        self.assertEqual(
            mock_get.call_args[0],
            ("https://api.exchangeratesapi.io/latest?base=CHF",),
        )

    def test_exchange_rates_someday(self, mock_get):
        """Exchange rates of a specific day hits the expected URL"""
        exchange_rates(dt.date(2019, 10, 12))
        self.assertEqual(
            mock_get.call_args[0],
            ("https://api.exchangeratesapi.io/2019-10-12?base=CHF",),
        )
