import datetime as dt

from django.conf import settings

from workbench.accounts.features import FEATURES


def workbench(request):
    today = dt.date.today()
    return {
        "WORKBENCH": settings.WORKBENCH,
        "FEATURES": FEATURES,
        "DEBUG": settings.DEBUG,
        "TESTING": settings.TESTING,
        "MAR08": (today.month, today.day) == (3, 8),
        "JUN": today.month == 6,
    }
