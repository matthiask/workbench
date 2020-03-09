import datetime as dt

from workbench.reporting.models import Accruals
from workbench.tools.validation import in_days


def create_accruals_for_last_month():
    today = dt.date.today()
    if today.day != 1:
        return
    Accruals.objects.for_cutoff_date(in_days(-1))
