from django.contrib.auth.decorators import login_required
from ninja import NinjaAPI

from workbench.accounts.api import router as accounts_router
from workbench.accounts.api_auth import user_auth
from workbench.contacts.api import router as contacts_router
from workbench.deals.api import router as deals_router
from workbench.invoices.api import router as invoices_router
from workbench.offers.api import router as offers_router
from workbench.planning.api import router as planning_router
from workbench.projects.api import router as projects_router
from workbench.reporting.api import router as reporting_router


api = NinjaAPI(
    title="Workbench",
    auth=user_auth(),
    docs_decorator=login_required,
    urls_namespace="api",
)
api.add_router("/", accounts_router)
api.add_router("/", contacts_router)
api.add_router("/", deals_router)
api.add_router("/", invoices_router)
api.add_router("/", offers_router)
api.add_router("/", planning_router)
api.add_router("/", projects_router)
api.add_router("/", reporting_router)
