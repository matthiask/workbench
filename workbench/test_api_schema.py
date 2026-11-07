import importlib
import inspect
from pathlib import Path

from django.test import SimpleTestCase
from ninja import Schema

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
