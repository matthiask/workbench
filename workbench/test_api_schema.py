import importlib
import inspect
from pathlib import Path
from unittest.mock import ANY

from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings
from ninja import Schema

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.api import api


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
