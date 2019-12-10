from django.conf import settings

from workbench.accounts.features import Features


def workbench(request):
    return {
        "WORKBENCH": settings.WORKBENCH,
        "FEATURES": Features,
        "DEBUG": settings.DEBUG,
    }
