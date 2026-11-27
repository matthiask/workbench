import ast
import importlib
import inspect
import re
from pathlib import Path
from unittest.mock import ANY

from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings
from django.urls import URLResolver, get_resolver
from ninja import Schema

from workbench import factories, generic
from workbench.accounts.features import FEATURES, F
from workbench.api import api


# Function views changing data; create, update and delete views are found
# by their class
WRITING_FUNCTION_VIEWS = {
    "accounts_api_tokens",
    "accounts_cli_login",
    "awt_absence_confirm",
    "contacts_organization_merge",
    "contacts_person_merge",
    "create_timestamp",
    "credit_control_export_debtors",
    "deals_deal_add_offer",
    "deals_deal_add_project",
    "deals_deal_remove_offer",
    "deals_deal_remove_project",
    "delete_timestamp",
    "invoices_reminders",
    "invoices_send_reminder",
    "logbook_loggedcost_create",
    "logbook_loggedhours_create",
    "notes_note_add",
    "offers_offer_copy",
    "planning_externalwork_create",
    "planning_milestone_create",
    "planning_plannedwork_create",
    "projects_project_logbook_batch_update_costs",
    "projects_project_logbook_batch_update_hours",
    "projects_project_pin",
    "projects_project_planning_batch_update",
    "projects_service_assign_service_type",
    "projects_service_pin",
    "projects_service_set_order",
    "split_timestamp",
}

# The API route doing what the web view does (maybe not all of it yet, the
# comments name the package which completes it)
API_ROUTES = {
    "awt_absence_create": "POST /api/absences/",
    "contacts_group_create": "POST /api/contacts/groups/",
    "contacts_group_update": "PATCH /api/contacts/groups/{group_id}/",
    "contacts_organization_create": "POST /api/contacts/organizations/",
    "contacts_organization_merge": (
        "POST /api/contacts/organizations/{organization_id}/merge/"
    ),
    "contacts_organization_postal_address": (
        "POST /api/contacts/organizations/{organization_id}/postal-address/"
    ),
    "contacts_organization_update": (
        "PATCH /api/contacts/organizations/{organization_id}/"
    ),
    "contacts_person_create": "POST /api/contacts/people/",
    "contacts_person_merge": "POST /api/contacts/people/{person_id}/merge/",
    # Changing and removing email addresses and phone numbers: package 16
    "contacts_person_update": "PATCH /api/contacts/people/{person_id}/",
    "create_timestamp": "POST /api/timestamps/",
    "deals_deal_add_offer": "POST /api/deals/{deal_id}/offers/",
    "deals_deal_add_project": "POST /api/deals/{deal_id}/projects/",
    "deals_deal_create": "POST /api/deals/",
    "deals_deal_delete": "DELETE /api/deals/{deal_id}/",
    "deals_deal_remove_offer": "POST /api/deals/{deal_id}/offers/remove/",
    "deals_deal_remove_project": "POST /api/deals/{deal_id}/projects/remove/",
    "deals_deal_set_status": "POST /api/deals/{deal_id}/status/",
    "deals_deal_update": "PATCH /api/deals/{deal_id}/",
    "delete_timestamp": "DELETE /api/timestamps/{timestamp}/",
    "hosting_server_create": "POST /api/hosting/servers/",
    "hosting_server_delete": "DELETE /api/hosting/servers/{server_id}/",
    "hosting_server_update": "PATCH /api/hosting/servers/{server_id}/",
    "hosting_site_add_contact": "POST /api/hosting/sites/{site_id}/contacts/",
    "hosting_site_create": "POST /api/hosting/sites/",
    "hosting_site_delete": "DELETE /api/hosting/sites/{site_id}/",
    "hosting_site_update": "PATCH /api/hosting/sites/{site_id}/",
    "hosting_sitecontact_delete": (
        "POST /api/hosting/sites/{site_id}/contacts/remove/"
    ),
    "hosting_sitecontact_update": (
        "PATCH /api/hosting/sites/{site_id}/contacts/{contact_id}/"
    ),
    "invoices_invoice_create": "POST /api/invoices/",
    "invoices_invoice_delete": "DELETE /api/invoices/{invoice_id}/",
    "invoices_invoice_postpone_reminders": (
        "POST /api/invoices/{invoice_id}/postpone-reminders/"
    ),
    "invoices_invoice_settle": "PATCH /api/invoices/{invoice_id}/",
    "invoices_invoice_update": "PATCH /api/invoices/{invoice_id}/",
    "invoices_recurringinvoice_create": "POST /api/recurring-invoices/",
    "invoices_recurringinvoice_delete": (
        "DELETE /api/recurring-invoices/{invoice_id}/"
    ),
    "invoices_recurringinvoice_update": "PATCH /api/recurring-invoices/{invoice_id}/",
    "logbook_loggedcost_create": "POST /api/logbook/costs/",
    "logbook_loggedcost_delete": "DELETE /api/logbook/costs/{cost_id}/",
    "logbook_loggedcost_move": "PATCH /api/logbook/costs/{cost_id}/",
    "logbook_loggedcost_update": "PATCH /api/logbook/costs/{cost_id}/",
    "logbook_loggedhours_create": "POST /api/logbook/hours/",
    "logbook_loggedhours_delete": "DELETE /api/logbook/hours/{hours_id}/",
    "logbook_loggedhours_move": "PATCH /api/logbook/hours/{hours_id}/",
    "logbook_loggedhours_update": "PATCH /api/logbook/hours/{hours_id}/",
    "notes_note_add": "POST /api/notes/",
    "notes_note_delete": "DELETE /api/notes/{note_id}/",
    "notes_note_update": "PATCH /api/notes/{note_id}/",
    "offers_offer_copy": "POST /api/offers/{offer_id}/copy/",
    "offers_offer_create": "POST /api/projects/{project_id}/offers/",
    "offers_offer_delete": "DELETE /api/offers/{offer_id}/",
    "offers_offer_update": "PATCH /api/offers/{offer_id}/",
    "planning_externalwork_create": (
        "POST /api/projects/{project_id}/planning/external-work/"
    ),
    "planning_externalwork_delete": "DELETE /api/planning/external-work/{work_id}/",
    "planning_externalwork_update": "PATCH /api/planning/external-work/{work_id}/",
    "planning_milestone_create": (
        "POST /api/projects/{project_id}/planning/milestones/"
    ),
    "planning_milestone_delete": "DELETE /api/planning/milestones/{milestone_id}/",
    "planning_milestone_update": "PATCH /api/planning/milestones/{milestone_id}/",
    "planning_plannedwork_create": "POST /api/projects/{project_id}/planning/work/",
    "planning_plannedwork_delete": "DELETE /api/planning/work/{work_id}/",
    "planning_plannedwork_update": "PATCH /api/planning/work/{work_id}/",
    "projects_project_create": "POST /api/projects/",
    "projects_project_createcost": "POST /api/logbook/costs/",
    "projects_project_createhours": "POST /api/logbook/hours/",
    "projects_project_createinvoice": "POST /api/invoices/",
    "projects_project_createoffer": "POST /api/projects/{project_id}/offers/",
    "projects_project_createservice": "POST /api/services/",
    "projects_project_createexternalwork": (
        "POST /api/projects/{project_id}/planning/external-work/"
    ),
    "projects_project_createmilestone": (
        "POST /api/projects/{project_id}/planning/milestones/"
    ),
    "projects_project_creatework": "POST /api/projects/{project_id}/planning/work/",
    "projects_project_logbook_batch_update_costs": (
        "POST /api/projects/{project_id}/logbook/move/"
    ),
    "projects_project_logbook_batch_update_hours": (
        "POST /api/projects/{project_id}/logbook/move/"
    ),
    "projects_project_planning_batch_update": "POST /api/planning/work/batch/",
    "projects_project_renumber_offers": (
        "POST /api/projects/{project_id}/offers/renumber/"
    ),
    "projects_project_update": "PATCH /api/projects/{project_id}/",
    "projects_service_assign_service_type": "PATCH /api/services/{service_id}/",
    "projects_service_delete": "DELETE /api/services/{service_id}/",
    "projects_service_merge": "POST /api/services/{service_id}/merge/",
    "projects_service_reassign_logbook": (
        "POST /api/services/{service_id}/reassign-logbook/"
    ),
    "projects_service_set_order": "POST /api/services/reorder/",
    "projects_service_update": "PATCH /api/services/{service_id}/",
}

# Web views without API route: either out of scope (see specs/complete-api)
# or the package which adds the route
NOT_IN_API = {
    "accounts_api_tokens": "out of scope: own profile (the API deletes tokens)",
    "accounts_cli_login": "out of scope: own profile (logs wb in)",
    "accounts_team_create": "package 19",
    "accounts_team_delete": "package 19",
    "accounts_team_update": "package 19",
    "accounts_update": "out of scope: own profile",
    "awt_absence_confirm": "out of scope: personnel administration",
    "awt_absence_delete": "package 18",
    "awt_absence_update": "package 18",
    "contacts_group_delete": "out of scope: deleting contacts",
    "contacts_organization_delete": "out of scope: deleting contacts",
    "contacts_person_delete": "out of scope: deleting contacts",
    "credit_control_creditentry_assign": "out of scope: bookkeeping",
    "credit_control_creditentry_create": "out of scope: bookkeeping",
    "credit_control_creditentry_delete": "out of scope: bookkeeping",
    "credit_control_creditentry_update": "out of scope: bookkeeping",
    "credit_control_creditentry_upload": "out of scope: bookkeeping",
    "credit_control_export_debtors": "out of scope: bookkeeping",
    "expenses_expensereport_create": "out of scope: bookkeeping",
    "expenses_expensereport_delete": "out of scope: bookkeeping",
    "expenses_expensereport_update": "out of scope: bookkeeping",
    "invoices_invoice_createservice": "package 05",
    "invoices_invoice_send": "out of scope: sending mail",
    "invoices_reminders": "out of scope: sending mail",
    "invoices_send_reminder": "out of scope: sending mail",
    "invoices_service_delete": "package 05",
    "invoices_service_update": "package 05",
    "logbook_break_create": "package 12",
    "logbook_break_delete": "package 12",
    "logbook_break_update": "package 12",
    "projects_budgettransfer_delete": "package 10",
    "projects_budgettransfer_update": "package 10",
    "projects_campaign_create": "package 11",
    "projects_campaign_delete": "package 11",
    "projects_campaign_update": "package 11",
    "projects_project_createbudgettransfer": "package 10",
    "projects_project_delete": "package 07",
    "projects_project_pin": "out of scope: own profile (pinned projects)",
    "projects_project_projected_invoices": "package 07",
    "projects_service_move": "package 08",
    "projects_service_pin": "out of scope: own profile (pinned services)",
    "split_timestamp": "package 23",
}


class APISchemaTest(SimpleTestCase):
    def test_unique_schema_names(self):
        """The OpenAPI document names schemas by their class name, classes
        with the same name overwrite each other there"""
        root = Path(__file__).parent
        modules = {
            ".".join(path.relative_to(root.parent).with_suffix("").parts)
            for pattern in ["*/api.py", "*/schemas.py", "api*.py", "search.py"]
            for path in root.glob(pattern)
        } | {"workbench.tools.api"}
        names = {}
        for module_name in sorted(modules):
            module = importlib.import_module(module_name)
            for name, obj in vars(module).items():
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Schema)
                    and obj.__module__ == module_name
                ):
                    with self.subTest(name=name):
                        self.assertNotIn(name, names, (module_name, names.get(name)))
                    names[name] = module_name

    def test_query_parameters_have_descriptions(self):
        """Every query parameter is described in the OpenAPI document (except
        ninja's limit and offset of paginated endpoints)"""
        schema = api.get_openapi_schema(path_prefix="/api/")
        missing = [
            f"{method.upper()} {path} {parameter['name']}"
            for path, operations in schema["paths"].items()
            for method, operation in operations.items()
            for parameter in operation.get("parameters", [])
            if parameter["in"] == "query"
            and parameter["name"] not in {"limit", "offset"}
            and not parameter.get("description")
        ]
        self.assertEqual(missing, [])

    def test_request_bodies_reject_unknown_fields(self):
        """Request bodies (also nested objects) reject unknown fields, data
        under a wrong key would be lost silently (``InputSchema``)"""
        schema = api.get_openapi_schema(path_prefix="/api/")
        components = schema["components"]["schemas"]

        def refs(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == "$ref":
                        yield value.rsplit("/", 1)[-1]
                    else:
                        yield from refs(value)
            elif isinstance(obj, list):
                for value in obj:
                    yield from refs(value)

        todo = [
            name
            for operations in schema["paths"].values()
            for operation in operations.values()
            for name in refs(operation.get("requestBody", {}))
        ]
        seen = set()
        while todo:
            if (name := todo.pop()) in seen:
                continue
            seen.add(name)
            todo.extend(refs(components[name]))
            with self.subTest(name=name):
                self.assertFalse(components[name].get("additionalProperties", True))
        self.assertIn("PlannedWorkIn", seen)

    def test_schema(self):
        """The OpenAPI document is generated without errors"""
        schema = api.get_openapi_schema(path_prefix="/api/")
        self.assertIn("/api/offers/{offer_id}/", schema["paths"])

        # Shared filters are described
        parameters = {
            parameter["name"]: parameter
            for parameter in schema["paths"]["/api/offers/"]["get"]["parameters"]
        }
        for name in ["q", "owned_by", "customer", "project", "period", "since"]:
            with self.subTest(name=name):
                self.assertTrue(parameters[name].get("description"), parameters[name])


class CoverageTest(SimpleTestCase):
    def test_web_views_writing_data_are_in_the_api(self):
        """Everything a user can change in the web interface can be changed
        through the API, or ``NOT_IN_API`` says why not (yet)"""

        skip = ("api/", "^admin/", "__debug__/")

        def walk(patterns):
            for pattern in patterns:
                if isinstance(pattern, URLResolver):
                    if not str(pattern.pattern).startswith(skip):
                        yield from walk(pattern.url_patterns)
                elif pattern.name:
                    yield pattern.name, getattr(pattern.callback, "view_class", None)

        views = dict(walk(get_resolver().url_patterns))
        self.assertEqual(WRITING_FUNCTION_VIEWS - views.keys(), set())
        writing = WRITING_FUNCTION_VIEWS | {
            name
            for name, view_class in views.items()
            if view_class
            and issubclass(
                view_class, (generic.CreateView, generic.UpdateView, generic.DeleteView)
            )
        }
        self.assertEqual(sorted(writing - API_ROUTES.keys() - NOT_IN_API.keys()), [])
        # Shrink NOT_IN_API when adding routes
        self.assertEqual(sorted(API_ROUTES.keys() & NOT_IN_API.keys()), [])
        self.assertEqual(sorted((API_ROUTES.keys() | NOT_IN_API.keys()) - writing), [])

        schema = api.get_openapi_schema(path_prefix="/api/")
        routes = {
            f"{method.upper()} {path}"
            for path, operations in schema["paths"].items()
            for method in operations
        }
        self.assertEqual(
            {name: route for name, route in API_ROUTES.items() if route not in routes},
            {},
        )
        self.assertEqual(
            {
                name: reason
                for name, reason in NOT_IN_API.items()
                if not re.fullmatch(r"out of scope: .+|package \d\d", reason)
            },
            {},
        )


class WarningCodesTest(SimpleTestCase):
    def test_warnings_have_codes(self):
        """Every warning has a stable kebab-case code, the API's
        ``ignore_warnings`` names them"""
        root = Path(__file__).parent
        calls = 0
        for path in sorted(root.rglob("*.py")):
            if path.name.startswith("test"):
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_warning"
                ):
                    continue
                calls += 1
                code = next(
                    (kw.value for kw in node.keywords if kw.arg == "code"), None
                )
                with self.subTest(path=str(path.relative_to(root)), line=node.lineno):
                    self.assertIsNotNone(code, "add_warning() without code=")
                    # Codes from variables (e.g. merge_warnings()) are fine
                    if isinstance(code, ast.Constant):
                        self.assertRegex(code.value, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertGreater(calls, 50)


class UnknownShortNamesTest(TestCase):
    def test_unknown_short_names(self):
        """Filters by short name reject unknown ones instead of finding
        nothing"""
        user = factories.UserFactory.create(_short_name="ab")
        self.client.force_login(user)
        for url, param in [
            ("/api/projects/", "owned_by"),
            ("/api/offers/", "owned_by"),
            ("/api/recurring-invoices/", "owned_by"),
            ("/api/deals/", "owned_by"),
            ("/api/deals/", "contributor"),
            ("/api/notes/", "created_by"),
            ("/api/absences/", "user"),
            ("/api/logbook/hours/", "rendered_by"),
        ]:
            with self.subTest(url=url, param=param):
                response = self.client.get(url, {param: "AB"})
                self.assertEqual(response.status_code, 200, response.content)
                response = self.client.get(url, {param: "xy"})
                self.assertEqual(response.status_code, 422, response.content)
                self.assertEqual(
                    response.json()["detail"][0]["loc"], ["query", "filters", param]
                )


class CodesTest(TestCase):
    def test_detail_by_code(self):
        """Projects, offers, invoices and deals are found by their ID or code"""
        project = factories.ProjectFactory.create()
        offer = factories.OfferFactory.create(project=project)
        invoice = factories.InvoiceFactory.create(
            project=project, customer=project.customer, contact=project.contact
        )
        without_project = factories.InvoiceFactory.create()
        deal = factories.DealFactory.create()
        self.client.force_login(project.owned_by)

        for url, obj in [
            ("/api/projects/{}/", project),
            ("/api/offers/{}/", offer),
            ("/api/invoices/{}/", invoice),
            ("/api/invoices/{}/", without_project),
            ("/api/deals/{}/", deal),
        ]:
            for value in [obj.pk, obj.code]:
                with self.subTest(url=url, value=value):
                    response = self.client.get(url.format(value))
                    self.assertEqual(response.status_code, 200, response.content)
                    self.assertEqual(response.json()["id"], obj.pk)
        self.assertEqual(self.client.get("/api/projects/1999-9999/").status_code, 404)
        self.assertEqual(self.client.get("/api/offers/nope/").status_code, 404)
        # Changing still works
        response = self.client.patch(
            f"/api/projects/{project.pk}/",
            {"title": "Renamed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)


class ErrorsTest(TestCase):
    def test_error_shape(self):
        """All errors are lists of locations and messages, like validation
        errors, and documented"""
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": [{"loc": [], "msg": ANY}]})

        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/api/offers/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": [{"loc": [], "msg": ANY}]})

        with override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER}):
            response = self.client.get("/api/invoices/")
        self.assertEqual(response.status_code, 403)
        [error] = response.json()["detail"]
        self.assertIn("feature", error["msg"])

        schema = api.get_openapi_schema(path_prefix="/api/")
        responses = schema["paths"]["/api/offers/"]["get"]["responses"]
        self.assertIn("4XX", responses)
        self.assertIn("Error", schema["components"]["schemas"])
