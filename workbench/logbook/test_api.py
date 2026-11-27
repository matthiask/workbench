import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.expenses.models import ExpenseReport
from workbench.invoices.models import Invoice
from workbench.logbook.models import Break, LoggedCost, LoggedHours
from workbench.projects.models import Project
from workbench.timer.models import Timestamp
from workbench.tools.validation import in_days


class LogbookAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_hours(self):
        """Logged hours can be filtered, the total includes all matches"""
        user = factories.UserFactory.create(_short_name="ab")
        offer = factories.OfferFactory.create()
        service = factories.ServiceFactory.create(
            title="Design", project=offer.project, offer=offer
        )
        mine = factories.LoggedHoursFactory.create(
            service=service,
            rendered_by=user,
            rendered_on=dt.date(2026, 10, 1),
            hours=2,
            description="Wireframes",
        )
        other = factories.LoggedHoursFactory.create(
            rendered_on=dt.date(2026, 9, 1), hours="1.5"
        )
        self.client.force_login(user)

        def ids(query=""):
            data = self.client.get(f"/api/logbook/hours/{query}").json()
            return [row["id"] for row in data["items"]]

        data = self.client.get("/api/logbook/hours/").json()
        self.assertEqual(data["total_hours"], "3.5")
        self.assertEqual(data["count"], 2)
        self.assertEqual([row["id"] for row in data["items"]], [mine.pk, other.pk])
        self.assertEqual(data["items"][0]["project"]["code"], service.project.code)
        self.assertEqual(
            data["items"][0]["project"]["customer"]["name"],
            service.project.customer.name,
        )
        self.assertEqual(data["items"][0]["service"], "Design")
        self.assertEqual(data["items"][0]["offer_id"], offer.pk)
        self.assertIsNone(data["items"][1]["offer_id"])
        self.assertEqual(data["items"][0]["rendered_by"], "ab")
        # When the entry was logged, not only when the work was done
        self.assertAlmostEqual(
            dt.datetime.fromisoformat(data["items"][0]["created_at"]),
            mine.created_at,
            delta=dt.timedelta(milliseconds=1),
        )

        # Pages of matches, the total and the count include all of them
        data = self.client.get("/api/logbook/hours/?limit=1&offset=1").json()
        self.assertEqual([row["id"] for row in data["items"]], [other.pk])
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["total_hours"], "3.5")
        # Entries with invoiced hours, for sanity checks
        mine.hours_for_invoicing = 3
        mine.save()
        data = self.client.get("/api/logbook/hours/?hours_for_invoicing=true").json()
        self.assertEqual([row["id"] for row in data["items"]], [mine.pk])
        self.assertEqual(data["items"][0]["hours_for_invoicing"], "3.0")
        self.assertEqual(data["total_hours"], "2.0")

        response = self.client.get("/api/logbook/hours/?limit=10001")
        self.assertEqual(response.status_code, 422)
        response = self.client.get("/api/logbook/hours/?offset=-1")
        self.assertEqual(response.status_code, 422)

        self.assertEqual(ids("?q=wireframes"), [mine.pk])
        self.assertEqual(ids(f"?project={service.project_id}"), [mine.pk])
        self.assertEqual(
            ids(f"?customer={other.service.project.customer_id}"), [other.pk]
        )
        self.assertEqual(ids(f"?service={other.service_id}"), [other.pk])
        offer = factories.OfferFactory.create(project=service.project)
        service.offer = offer
        service.save()
        self.assertEqual(ids(f"?offer={offer.pk}"), [mine.pk])
        self.assertEqual(ids("?rendered_by=AB"), [mine.pk])
        self.assertEqual(ids("?since=2026-09-15"), [mine.pk])
        self.assertEqual(ids("?until=2026-09-15"), [other.pk])

    def test_invoiced(self):
        """Logged hours have their invoice and can be filtered by it"""
        service = factories.ServiceFactory.create()
        invoiced = factories.LoggedHoursFactory.create(service=service)
        invoice = factories.InvoiceFactory.create(
            project=service.project,
            customer=service.project.customer,
            contact=service.project.contact,
            type=Invoice.SERVICES,
        )
        invoice.create_services_from_logbook([service])
        not_invoiced = factories.LoggedHoursFactory.create(service=service)
        self.client.force_login(service.project.owned_by)

        def rows(query=""):
            data = self.client.get(f"/api/logbook/hours/{query}").json()
            return {row["id"]: row for row in data["items"]}

        data = rows()
        self.assertEqual(
            data[invoiced.pk]["invoice"],
            {"id": invoice.pk, "code": invoice.code, "status": "in_preparation"},
        )
        self.assertIsNotNone(data[invoiced.pk]["archived_at"])
        self.assertIsNone(data[not_invoiced.pk]["invoice"])
        self.assertIsNone(data[not_invoiced.pk]["archived_at"])

        self.assertEqual(set(rows("?invoiced=true")), {invoiced.pk})
        self.assertEqual(set(rows("?invoiced=false")), {not_invoiced.pk})

    def test_costs(self):
        """Logged costs can be filtered, the totals include all matches"""
        user = factories.UserFactory.create(_short_name="ab")
        hosting = factories.LoggedCostFactory.create(
            rendered_by=user,
            cost=100,
            third_party_costs=80,
            description="Hosting",
        )
        expense = factories.LoggedCostFactory.create(
            cost=50, are_expenses=True, description="Train ticket"
        )
        self.client.force_login(user)

        def ids(query=""):
            data = self.client.get(f"/api/logbook/costs/{query}").json()
            return {row["id"] for row in data["items"]}

        data = self.client.get("/api/logbook/costs/").json()
        self.assertEqual(data["total_cost"], "150.00")
        self.assertEqual(data["total_third_party_costs"], "80.00")
        self.assertEqual(data["count"], 2)
        created = {
            row["id"]: dt.datetime.fromisoformat(row["created_at"])
            for row in data["items"]
        }
        self.assertAlmostEqual(
            created[hosting.pk],
            hosting.created_at,
            delta=dt.timedelta(milliseconds=1),
        )

        self.assertEqual(ids("?q=hosting"), {hosting.pk})
        self.assertEqual(ids("?expenses=true"), {expense.pk})
        self.assertEqual(ids("?rendered_by=AB"), {hosting.pk})
        self.assertEqual(ids(f"?project={expense.service.project_id}"), {expense.pk})


class LogbookChangesAPITest(TestCase):
    fixtures = ["exchangerates.json"]

    def tearDown(self):
        deactivate_all()

    def post(self, url, data, *, ignore=()):
        if ignore:
            url += ("&" if "?" in url else "?") + "&".join(
                f"ignore_warnings={code}" for code in ignore
            )
        return self.client.post(url, data, content_type="application/json")

    def test_create_hours(self):
        """Hours are logged like in the web interface, warnings are errors
        unless they're ignored by their code"""
        service = factories.ServiceFactory.create()
        user = service.project.owned_by
        self.client.force_login(user)
        data = {"service": service.pk, "hours": 1.5, "description": "Wireframes"}

        response = self.post("/api/logbook/hours/?dry_run=1", data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["id"])
        self.assertEqual(LoggedHours.objects.count(), 0)

        response = self.post("/api/logbook/hours/", data)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        entry = LoggedHours.objects.get()
        self.assertEqual(result["id"], entry.pk)
        self.assertEqual(result["hours"], "1.5")
        self.assertEqual(entry.rendered_by, user)
        self.assertEqual(entry.rendered_on, dt.date.today())
        self.assertEqual(entry.created_by, user)
        self.assertIsNone(entry.hours_for_invoicing)

        response = self.post("/api/logbook/hours/", data)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error.get("code") for error in response.json()["detail"]],
            ["maybe-duplicate"],
        )
        response = self.post("/api/logbook/hours/", data, ignore=["maybe-duplicate"])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(LoggedHours.objects.count(), 2)

    def test_create_hours_errors(self):
        """Errors of the form and unknown users are located at their field"""
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        def errors(**kwargs):
            data = {"service": service.pk, "hours": 1, "description": "Test"}
            response = self.post("/api/logbook/hours/", data | kwargs)
            self.assertEqual(response.status_code, 422)
            return [error["loc"][-1] for error in response.json()["detail"]]

        self.assertEqual(errors(rendered_on=in_days(10).isoformat()), ["rendered_on"])
        self.assertEqual(errors(rendered_by="nobody"), ["rendered_by"])
        self.assertEqual(errors(hours=0), ["hours"])
        self.assertEqual(errors(service_title="New"), ["service_title"])

        service.allow_logging = False
        service.save()
        self.assertEqual(errors(), ["service"])

        response = self.post(
            "/api/logbook/hours/", {"service": 0, "hours": 1, "description": "Test"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(LoggedHours.objects.count(), 0)

    def test_query_parameters_of_the_web_interface(self):
        """Query parameters only meant for the web interface's form (copying
        entries, timestamps of the timer) are ignored"""
        entry = factories.LoggedHoursFactory.create(description="Original")
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        response = self.post(
            f"/api/logbook/hours/?copy={entry.pk}&detected_ends_at=2026-11-20T12:00:00",
            {"service": service.pk, "hours": 1, "description": "Test"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["description"], "Test")
        self.assertEqual(Timestamp.objects.count(), 0)

    def test_update_hours(self):
        """Changes are validated like in the web interface, hours of past
        weeks keep their hours"""
        entry = factories.LoggedHoursFactory.create(description="Before", hours=1)
        self.client.force_login(entry.rendered_by)
        url = f"/api/logbook/hours/{entry.pk}/"

        def patch(data, query=""):
            return self.client.patch(
                f"{url}{query}", data, content_type="application/json"
            )

        response = patch({"description": "After"}, "?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], entry.pk)
        self.assertEqual(response.json()["description"], "After")
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Before")

        response = patch({"description": "After", "hours_for_invoicing": 2})
        self.assertEqual(response.status_code, 200, response.content)
        entry.refresh_from_db()
        self.assertEqual(entry.description, "After")
        self.assertEqual(entry.hours, 1)
        self.assertEqual(entry.hours_for_invoicing, 2)

        response = patch({"hours_for_invoicing": 0.5})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error.get("code") for error in response.json()["detail"]],
            ["hours-for-invoicing-lower"],
        )
        response = patch(
            {"hours_for_invoicing": None}, "?ignore_warnings=hours-for-invoicing-lower"
        )
        self.assertEqual(response.status_code, 200, response.content)
        entry.refresh_from_db()
        self.assertIsNone(entry.hours_for_invoicing)

        LoggedHours.objects.filter(pk=entry.pk).update(rendered_on=in_days(-30))
        response = patch({"hours": 2})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "hours"]],
        )
        response = patch({"description": "Later"})
        self.assertEqual(response.status_code, 200, response.content)

    def test_delete_hours(self):
        """Hours are deleted like in the web interface, the reasons why not
        are errors"""
        entry = factories.LoggedHoursFactory.create()
        self.client.force_login(entry.rendered_by)
        url = f"/api/logbook/hours/{entry.pk}/"

        response = self.client.delete(f"{url}?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(LoggedHours.objects.filter(pk=entry.pk).exists())

        LoggedHours.objects.filter(pk=entry.pk).update(rendered_on=in_days(-30))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["path", "hours_id"],
                    "msg": "Cannot delete logged hours from past weeks.",
                }
            ],
        )

        LoggedHours.objects.filter(pk=entry.pk).update(rendered_on=dt.date.today())
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], entry.pk)
        self.assertFalse(LoggedHours.objects.filter(pk=entry.pk).exists())

    def test_create_cost(self):
        """Costs are logged like in the web interface, warnings are errors
        unless they're ignored by their code"""
        service = factories.ServiceFactory.create()
        user = service.project.owned_by
        self.client.force_login(user)
        data = {
            "service": service.pk,
            "cost": 100,
            "third_party_costs": 120,
            "description": "Hosting",
        }

        response = self.post("/api/logbook/costs/", data)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error.get("code") for error in response.json()["detail"]],
            ["third-party-costs-higher"],
        )
        response = self.post(
            "/api/logbook/costs/?dry_run=1", data, ignore=["third-party-costs-higher"]
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["id"])
        self.assertEqual(LoggedCost.objects.count(), 0)

        response = self.post(
            "/api/logbook/costs/", data, ignore=["third-party-costs-higher"]
        )
        self.assertEqual(response.status_code, 200, response.content)
        entry = LoggedCost.objects.get()
        self.assertEqual(response.json()["cost"], "100.00")
        self.assertEqual(entry.rendered_by, user)
        self.assertEqual(entry.created_by, user)
        self.assertEqual(entry.rendered_on, dt.date.today())
        self.assertFalse(entry.are_expenses)

        response = self.post(
            "/api/logbook/costs/",
            {
                "service": service.pk,
                "cost": 10,
                "are_expenses": True,
                "description": "Taxi",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"][-1] for error in response.json()["detail"]],
            ["third_party_costs"],
        )

    @override_settings(
        FEATURES={FEATURES.EXPENSES: F.NEVER, FEATURES.FOREIGN_CURRENCIES: F.NEVER}
    )
    def test_cost_features(self):
        """Fields of features the user doesn't have are errors, not ignored"""
        service = factories.ServiceFactory.create()
        self.client.force_login(service.project.owned_by)

        response = self.post(
            "/api/logbook/costs/",
            {
                "service": service.pk,
                "cost": 10,
                "third_party_costs": 10,
                "are_expenses": True,
                "description": "Taxi",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"][-1] for error in response.json()["detail"]],
            ["are_expenses"],
        )
        self.assertEqual(LoggedCost.objects.count(), 0)

    def test_update_and_delete_cost(self):
        """Costs of expense reports keep their expenses and aren't deleted"""
        entry = factories.LoggedCostFactory.create(
            are_expenses=True, third_party_costs=10, description="Taxi"
        )
        user = entry.rendered_by
        self.client.force_login(user)
        url = f"/api/logbook/costs/{entry.pk}/"

        def patch(data):
            return self.client.patch(url, data, content_type="application/json")

        response = patch({"cost": 12, "description": "Taxi to the airport"})
        self.assertEqual(response.status_code, 200, response.content)
        entry.refresh_from_db()
        self.assertEqual(entry.cost, 12)
        self.assertEqual(entry.description, "Taxi to the airport")

        report = ExpenseReport.objects.create(created_by=user, owned_by=user)
        report.expenses.set([entry])
        response = patch({"third_party_costs": 11})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"][-1] for error in response.json()["detail"]],
            ["third_party_costs"],
        )
        response = patch({"description": "Taxi"})
        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["path", "cost_id"]],
        )

        report.expenses.clear()
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(LoggedCost.objects.filter(pk=entry.pk).exists())


class LogbookMoveAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def patch(self, url, data, query=""):
        return self.client.patch(f"{url}{query}", data, content_type="application/json")

    def test_move_hours_to_another_project(self):
        """A service of another project moves the hours through the move form
        of the web interface: archived entries and closed projects refused"""
        entry = factories.LoggedHoursFactory.create(description="Before")
        service = entry.service
        target = factories.ServiceFactory.create()
        self.client.force_login(entry.rendered_by)
        url = f"/api/logbook/hours/{entry.pk}/"

        response = self.patch(url, {"service": target.pk}, "?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["project"]["id"], target.project_id)
        entry.refresh_from_db()
        self.assertEqual(entry.service, service)

        response = self.patch(url, {"service": target.pk, "description": "After"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["service_id"], target.pk)
        self.assertEqual(response.json()["description"], "After")
        entry.refresh_from_db()
        self.assertEqual(entry.service, target)
        self.assertEqual(entry.description, "After")

        # Errors of the other fields leave the entry where it was
        other = factories.ServiceFactory.create()
        response = self.patch(url, {"service": other.pk, "hours": 0})
        self.assertEqual(response.status_code, 422)
        entry.refresh_from_db()
        self.assertEqual(entry.service, target)

        closed = factories.ServiceFactory.create()
        Project.objects.filter(pk=closed.project_id).update(closed_on=in_days(0))
        response = self.patch(url, {"service": closed.pk})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "service"]],
        )

        Project.objects.filter(pk=target.project_id).update(closed_on=in_days(0))
        response = self.patch(url, {"service": other.pk})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["msg"] for error in response.json()["detail"]],
            ["Cannot move logbook entries of closed projects."],
        )

        Project.objects.filter(pk=target.project_id).update(closed_on=None)
        LoggedHours.objects.filter(pk=entry.pk).update(archived_at=timezone.now())
        response = self.patch(url, {"service": other.pk})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["msg"] for error in response.json()["detail"]],
            ["Cannot move archived logbook entries."],
        )
        entry.refresh_from_db()
        self.assertEqual(entry.service, target)

    def test_move_invoiced_entries(self):
        """Entries on an invoice are refused when moving them to another
        project or to another service of the project"""
        service = factories.ServiceFactory.create()
        project = service.project
        target = factories.ServiceFactory.create(project=project)
        invoice = factories.InvoiceFactory.create(
            project=project, type=Invoice.SERVICES
        )
        invoice_service = invoice.services.create(title="Test", cost=50)
        hours = factories.LoggedHoursFactory.create(
            service=service, invoice_service=invoice_service
        )
        cost = factories.LoggedCostFactory.create(
            service=service, invoice_service=invoice_service
        )
        self.client.force_login(hours.rendered_by)

        other = factories.ServiceFactory.create()
        for url in [
            f"/api/logbook/hours/{hours.pk}/",
            f"/api/logbook/costs/{cost.pk}/",
        ]:
            with self.subTest(url=url):
                response = self.patch(url, {"service": other.pk})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    [error["msg"] for error in response.json()["detail"]],
                    ["Cannot move logbook entries which are on an invoice."],
                )

        response = self.client.post(
            f"/api/projects/{project.pk}/logbook/move/",
            {"kind": "hours", "entries": [hours.pk], "service": target.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "entries"]],
        )

        hours.refresh_from_db()
        self.assertEqual(hours.service, service)
        cost.refresh_from_db()
        self.assertEqual(cost.service, service)

    def test_move_cost_to_another_project(self):
        """Costs move to services of other projects too"""
        entry = factories.LoggedCostFactory.create()
        target = factories.ServiceFactory.create()
        self.client.force_login(entry.rendered_by)

        response = self.patch(f"/api/logbook/costs/{entry.pk}/", {"service": target.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["project"]["id"], target.project_id)
        entry.refresh_from_db()
        self.assertEqual(entry.service, target)

    def test_batch_move(self):
        """Entries of a project move to another service of the same project
        through the batch form of the web interface"""
        service = factories.ServiceFactory.create()
        project = service.project
        target = factories.ServiceFactory.create(project=project)
        hours = factories.LoggedHoursFactory.create(service=service)
        archived = factories.LoggedHoursFactory.create(service=service)
        LoggedHours.objects.filter(pk=archived.pk).update(archived_at=timezone.now())
        cost = factories.LoggedCostFactory.create(service=service)
        self.client.force_login(hours.rendered_by)
        url = f"/api/projects/{project.pk}/logbook/move/"

        def post(data, query=""):
            return self.client.post(
                f"{url}{query}", data, content_type="application/json"
            )

        data = {"kind": "hours", "entries": [hours.pk], "service": target.pk}
        response = post(data, "?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            [(row["id"], row["service_id"]) for row in response.json()],
            [(hours.pk, target.pk)],
        )
        hours.refresh_from_db()
        self.assertEqual(hours.service, service)

        response = post(data)
        self.assertEqual(response.status_code, 200, response.content)
        hours.refresh_from_db()
        self.assertEqual(hours.service, target)

        # Archived entries and costs aren't hours of this project to move
        response = post(data | {"entries": [archived.pk, cost.pk]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            {tuple(error["loc"]) for error in response.json()["detail"]},
            {("body", "data", "entries")},
        )

        response = post({"kind": "costs", "entries": [cost.pk], "service": target.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]["cost"], "10.00")
        cost.refresh_from_db()
        self.assertEqual(cost.service, target)

        # Services of other projects are refused
        other = factories.ServiceFactory.create()
        response = post(data | {"service": other.pk})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["loc"] for error in response.json()["detail"]],
            [["body", "data", "service"]],
        )

        Project.objects.filter(pk=project.pk).update(closed_on=in_days(0))
        response = post(data | {"service": service.pk})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["msg"] for error in response.json()["detail"]],
            ["Cannot move logbook entries of closed projects."],
        )
        hours.refresh_from_db()
        self.assertEqual(hours.service, target)


def _at(day, time):
    return timezone.make_aware(dt.datetime.combine(day, dt.time.fromisoformat(time)))


class BreaksAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def _break(self, user, day=None, starts_at="12:00", ends_at="12:45", **kwargs):
        day = day or dt.date.today()
        return Break.objects.create(
            user=user,
            starts_at=_at(day, starts_at),
            ends_at=_at(day, ends_at),
            **kwargs,
        )

    def test_list(self):
        """Breaks of everyone, filtered like logged hours; the total includes
        all matches"""
        user = factories.UserFactory.create(_short_name="ab")
        other = factories.UserFactory.create(_short_name="cd")
        mine = self._break(user, description="Lunch")
        older = self._break(user, day=dt.date(2026, 9, 1), ends_at="12:15")
        others = self._break(other, starts_at="15:00", ends_at="15:10")
        self.client.force_login(user)

        def get(query=""):
            response = self.client.get(f"/api/logbook/breaks/{query}")
            self.assertEqual(response.status_code, 200, response.content)
            return response.json()

        data = get()
        self.assertEqual(
            [row["id"] for row in data["items"]], [others.pk, mine.pk, older.pk]
        )
        self.assertEqual(data["count"], 3)
        self.assertEqual(data["total_minutes"], 70)
        row = data["items"][1]
        self.assertEqual(row["user"], "ab")
        self.assertEqual(row["day"], dt.date.today().isoformat())
        self.assertEqual(row["minutes"], 45)
        self.assertEqual(row["description"], "Lunch")
        self.assertEqual(dt.datetime.fromisoformat(row["starts_at"]), mine.starts_at)
        self.assertTrue(row["url"].endswith(mine.get_absolute_url()))

        data = get("?user=AB")
        self.assertEqual([row["id"] for row in data["items"]], [mine.pk, older.pk])
        self.assertEqual(data["total_minutes"], 60)
        data = get("?user=ab&period=2026-09")
        self.assertEqual([row["id"] for row in data["items"]], [older.pk])
        data = get("?q=lunch")
        self.assertEqual([row["id"] for row in data["items"]], [mine.pk])

        response = self.client.get("/api/logbook/breaks/?user=nobody")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["query", "filters", "user"]
        )

    def test_create(self):
        """Breaks are created for yourself with the web interface's form"""
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def post(data, query=""):
            return self.client.post(
                f"/api/logbook/breaks/{query}", data, content_type="application/json"
            )

        data = {"starts_at": "12:00", "ends_at": "12:30", "description": "Lunch"}
        response = post(data, "?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["id"])
        self.assertIsNone(response.json()["url"])
        self.assertEqual(response.json()["minutes"], 30)
        self.assertFalse(Break.objects.exists())

        response = post(data)
        self.assertEqual(response.status_code, 200, response.content)
        brk = Break.objects.get()
        self.assertEqual(response.json()["id"], brk.pk)
        self.assertEqual(brk.user, user)
        self.assertEqual(brk.starts_at, _at(dt.date.today(), "12:00"))
        self.assertEqual(brk.description, "Lunch")

        # Query parameters of the timer are ignored, no timestamps
        response = post(
            {"day": in_days(-1).isoformat(), "starts_at": "15:00", "ends_at": "15:10"},
            "?detected_ends_at=2026-11-20T12:00:00",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["day"], in_days(-1).isoformat())
        self.assertEqual(Timestamp.objects.count(), 0)

        response = post({"day": "2010-01-01", "starts_at": "12:00", "ends_at": "13:00"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["body", "data", "day"],
                    "msg": "Breaks have to be logged promptly.",
                }
            ],
        )
        response = post({"starts_at": "13:00", "ends_at": "12:00"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "ends_at"]
        )
        response = post({"starts_at": "12:00"})
        self.assertEqual(response.status_code, 422)
        response = post({**data, "user": "ab"})
        self.assertEqual(response.status_code, 422)

    def test_update(self):
        """Own breaks are changed with the web interface's form"""
        user = factories.UserFactory.create()
        brk = self._break(user, description="Before")
        self.client.force_login(user)
        url = f"/api/logbook/breaks/{brk.pk}/"

        def patch(data, query=""):
            return self.client.patch(
                f"{url}{query}", data, content_type="application/json"
            )

        response = patch({"ends_at": "13:00", "description": "After"}, "?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["minutes"], 60)
        brk.refresh_from_db()
        self.assertEqual(brk.description, "Before")

        response = patch({"ends_at": "13:00", "description": "After"})
        self.assertEqual(response.status_code, 200, response.content)
        brk.refresh_from_db()
        self.assertEqual(brk.description, "After")
        self.assertEqual(brk.starts_at, _at(dt.date.today(), "12:00"))
        self.assertEqual(brk.ends_at, _at(dt.date.today(), "13:00"))

        # Moving to another day keeps the times
        response = patch({"day": in_days(-1).isoformat(), "description": None})
        self.assertEqual(response.status_code, 200, response.content)
        brk.refresh_from_db()
        self.assertEqual(brk.starts_at, _at(in_days(-1), "12:00"))
        self.assertEqual(brk.description, "")

        response = patch({"starts_at": "14:00"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "ends_at"]
        )

        # Others' breaks are refused like in the web interface
        other = self._break(factories.UserFactory.create())
        response = self.client.patch(
            f"/api/logbook/breaks/{other.pk}/",
            {"description": "Mine"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            [
                {
                    "loc": ["path", "break_id"],
                    "msg": "Cannot modify breaks of other users.",
                }
            ],
        )
        other.refresh_from_db()
        self.assertEqual(other.description, "")

    def test_delete(self):
        """Own breaks are deleted like in the web interface"""
        user = factories.UserFactory.create()
        brk = self._break(user, description="Twice")
        other = self._break(factories.UserFactory.create())
        self.client.force_login(user)

        response = self.client.delete(f"/api/logbook/breaks/{other.pk}/")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["msg"], "Cannot modify breaks of other users."
        )
        self.assertTrue(Break.objects.filter(pk=other.pk).exists())

        url = f"/api/logbook/breaks/{brk.pk}/"
        response = self.client.delete(f"{url}?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], brk.pk)
        self.assertTrue(Break.objects.filter(pk=brk.pk).exists())

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["description"], "Twice")
        self.assertFalse(Break.objects.filter(pk=brk.pk).exists())
        self.assertEqual(self.client.delete(url).status_code, 404)
