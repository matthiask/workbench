from django.conf import settings

from workbench.accounts.permissions import Permissions


def workbench(request):
    return {"WORKBENCH": settings.WORKBENCH, "PERMISSIONS": Permissions}
