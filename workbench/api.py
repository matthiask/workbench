from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils.translation import gettext
from ninja import NinjaAPI
from ninja.errors import HttpError

from workbench.accounts.api import router as accounts_router
from workbench.accounts.api_auth import user_auth
from workbench.api_keys import router as choices_router
from workbench.awt.api import router as awt_router
from workbench.contacts.api import router as contacts_router
from workbench.deals.api import router as deals_router
from workbench.invoices.api import router as invoices_router
from workbench.logbook.api import router as logbook_router
from workbench.notes.api import router as notes_router
from workbench.offers.api import router as offers_router
from workbench.planning.api import router as planning_router
from workbench.projects.api import router as projects_router
from workbench.reporting.api import router as reporting_router
from workbench.search import router as search_router
from workbench.timer.api import router as timer_router


ERROR_SCHEMA = {
    "type": "object",
    "properties": {
        "detail": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "loc": {
                        "type": "array",
                        "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                        "description": "Where the error is, e.g. body, data, title;"
                        " empty for errors of the whole request.",
                    },
                    "msg": {"type": "string"},
                    "code": {
                        "type": "string",
                        "description": "The code of warnings of the web"
                        " interface, which ignore_warnings takes.",
                    },
                },
                "required": ["loc", "msg"],
            },
        }
    },
    "required": ["detail"],
}


class WorkbenchAPI(NinjaAPI):
    def get_openapi_schema(self, **kwargs):
        """All errors share the shape of validation errors"""
        schema = super().get_openapi_schema(**kwargs)
        schema.setdefault("components", {}).setdefault("schemas", {})["Error"] = (
            ERROR_SCHEMA
        )
        for operations in schema["paths"].values():
            for operation in operations.values():
                operation.setdefault("responses", {})["4XX"] = {
                    "description": "Not authenticated (401), not allowed (403),"
                    " not found (404), or invalid (422, warnings carry their"
                    " code)",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    },
                }
        return schema


api = WorkbenchAPI(
    title="Workbench",
    auth=user_auth(),
    docs_decorator=login_required,
    urls_namespace="api",
)


def _error(request, message, status):
    return api.create_response(
        request, {"detail": [{"loc": [], "msg": message}]}, status=status
    )


@api.exception_handler(HttpError)
def http_error(request, exc):
    return _error(request, str(exc), exc.status_code)


@api.exception_handler(Http404)
def not_found(request, exc):
    return _error(request, gettext("Not found."), 404)


api.add_router("/", accounts_router)
api.add_router("/", awt_router)
api.add_router("/", choices_router)
api.add_router("/", contacts_router)
api.add_router("/", deals_router)
api.add_router("/", invoices_router)
api.add_router("/", logbook_router)
api.add_router("/", notes_router)
api.add_router("/", offers_router)
api.add_router("/", planning_router)
api.add_router("/", projects_router)
api.add_router("/", reporting_router)
api.add_router("/", search_router)
api.add_router("/", timer_router)
