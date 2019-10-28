import datetime as dt

from workbench.accruals.models import Accrual, CutoffDate


def create_accruals_for_last_month():
    today = dt.date.today()
    if today.day != 1:
        return
    date, _ = CutoffDate.objects.get_or_create(day=today - dt.timedelta(days=1))
    Accrual.objects.generate_accruals(cutoff_date=date.day)
