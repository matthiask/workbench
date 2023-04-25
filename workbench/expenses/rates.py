import datetime as dt

import requests


def exchange_rates(day=None):
    today = dt.date.today()
    day = day or today
    url = f"https://cdn.jsdelivr.net/gh/fawazahmed0/currency-api@1/{'latest' if day == today else day.isoformat()}/currencies/chf.json"
    data = requests.get(url, timeout=2).json()
    # Format from old api.exchangeratesapi.io endpoint
    return {
        "base": "CHF",
        "date": day.isoformat(),
        "rates": {curr.upper(): rate for curr, rate in data["chf"].items()}
        if data
        else {},
    }
