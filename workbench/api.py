from django.contrib.auth.decorators import login_required
from ninja import NinjaAPI
from ninja.security import django_auth

from workbench.planning.api import router as planning_router
from workbench.reporting.api import router as reporting_router


api = NinjaAPI(
    title="Workbench",
    auth=django_auth,
    docs_decorator=login_required,
    urls_namespace="api",
)
api.add_router("/", planning_router)
api.add_router("/", reporting_router)
