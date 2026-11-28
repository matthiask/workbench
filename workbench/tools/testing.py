import datetime as dt

from django.contrib.messages import get_messages


def messages(response):
    return [m.message for m in get_messages(response.wsgi_request)]


def check_code(test, base_url):
    def code(param, status_code=200):
        response = test.client.get(f"{base_url}?{param}")
        test.assertEqual(response.status_code, status_code)

    return code


def weekday(day=None):
    """The day (default today) or the following Monday if it's on a weekend;
    absences with more days than weekdays warn"""
    day = day or dt.date.today()
    return day + dt.timedelta(days=7 - day.weekday() if day.weekday() >= 5 else 0)
