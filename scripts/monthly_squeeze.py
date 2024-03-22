import datetime as dt
import subprocess
from itertools import pairwise


_year_from = 2023
_month = dt.timedelta(days=31)
_day = dt.timedelta(days=1)
_today = dt.date.today()


def monthly(day):
    while True:
        yield day
        day += _month
        day = day.replace(day=1)


def months():
    for start, end in pairwise(monthly(dt.date(_year_from, 1, 1))):
        yield start, end - _day


for start, end in months():
    if end >= _today:
        break

    cmd = [
        "venv/bin/python",
        "manage.py",
        "squeeze",
        "--range",
        f'{start.strftime("%Y%m%d")}-{end.strftime("%Y%m%d")}',
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
