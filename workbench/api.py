from django.contrib.auth.decorators import login_required
from ninja import NinjaAPI
from ninja.security import HttpBearer, django_auth

from workbench.accounts.models import APIToken
from workbench.offers.api import router as offers_router
from workbench.planning.api import router as planning_router
from workbench.projects.api import router as projects_router
from workbench.reporting.api import router as reporting_router


class UserToken(HttpBearer):
    """Personal API tokens, e.g. for the command line interface"""

    def authenticate(self, request, token):
        if user := APIToken.objects.user_for(token):
            request.user = user
            return user
        return None


api = NinjaAPI(
    title="Workbench",
    # Tokens first, the session authentication fails without a CSRF token
    auth=[UserToken(), django_auth],
    docs_decorator=login_required,
    urls_namespace="api",
)
api.add_router("/", offers_router)
api.add_router("/", planning_router)
api.add_router("/", projects_router)
api.add_router("/", reporting_router)
