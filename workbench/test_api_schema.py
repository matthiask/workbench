import importlib
import inspect
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from ninja import Schema

from workbench import factories
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
