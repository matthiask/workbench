import datetime as dt

from workbench.invoices.utils import recurring
from workbench.reporting.models import Accruals


def create_accruals_for_last_month():
    today = dt.date.today()
    start = today.replace(year=today.year - 2, day=1)

    for day in recurring(start, "monthly"):
        if day > today:
            break
        Accruals.objects.for_cutoff_date(day - dt.timedelta(days=1))
