import datetime as dt

from workbench.reporting.models import Accruals


def create_accruals_for_last_month():
    today = dt.date.today()
    if today.day != 1:
        return
    Accruals.objects.for_cutoff_date(dt.date.today() - dt.timedelta(days=1))
