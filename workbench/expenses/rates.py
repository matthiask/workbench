import requests


def exchange_rates(day=None):
    url = "https://api.exchangeratesapi.io/{}?base=CHF".format(
        day.isoformat() if day else "latest"
    )
    return requests.get(url, timeout=2).json()
