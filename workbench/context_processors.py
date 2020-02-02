from django.conf import settings

from workbench.accounts.features import FEATURES


def workbench(request):
    return {
        "WORKBENCH": settings.WORKBENCH,
        "FEATURES": FEATURES,
        "DEBUG": settings.DEBUG,
        "TESTING": settings.TESTING,
    }
