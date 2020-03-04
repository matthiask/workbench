import datetime as dt
from collections import defaultdict

from workbench.deals.models import Deal


def accepted_deals(date_range, *, users=None):
    by_user = defaultdict(list)
    queryset = Deal.objects.filter(
        status=Deal.ACCEPTED, closed_on__range=date_range
    ).select_related("customer", "contact__organization", "owned_by")

    if users is not None:
        queryset = queryset.filter(owned_by__in=users)

    for deal in queryset:
        by_user[deal.owned_by].append(deal)

    deals = [
        {
            "user": user,
            "deals": deals,
            "count": len(deals),
            "sum": sum(deal.value for deal in deals),
        }
        for user, deals in by_user.items()
    ]

    return {
        "by_user": sorted(deals, key=lambda row: row["sum"], reverse=True),
        "sum": sum(row["sum"] for row in deals),
        "count": sum(row["count"] for row in deals),
    }


def test():
    from pprint import pprint

    pprint(accepted_deals([dt.date(2020, 1, 1), dt.date(2020, 3, 31)]))
