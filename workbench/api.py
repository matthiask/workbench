from django.contrib.auth.decorators import login_required
from ninja import NinjaAPI
from ninja.security import django_auth


api = NinjaAPI(
    title="Workbench",
    auth=django_auth,
    docs_decorator=login_required,
    urls_namespace="api",
)
