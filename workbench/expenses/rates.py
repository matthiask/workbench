from django.conf import settings

import requests


def exchange_rates(day=None):
    url = "https://api.exchangeratesapi.io/{}?base={}".format(
        day.isoformat() if day else "latest",
        settings.WORKBENCH.CURRENCY,
    )
    return requests.get(url, timeout=2).json()
