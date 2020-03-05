import datetime as dt
from collections import defaultdict

from django.db.models import Prefetch

from workbench.deals.models import Deal, Value
from workbench.tools.models import Z


def accepted_deals(date_range, *, users=None):
    queryset = (
        Deal.objects.filter(status=Deal.ACCEPTED, closed_on__range=date_range)
        .select_related("customer", "contact__organization", "owned_by")
        .prefetch_related(
            Prefetch("values", queryset=Value.objects.select_related("type"))
        )
    )

    if users is not None:
        queryset = queryset.filter(owned_by__in=users)

    by_user = defaultdict(list)
    by_month_and_valuetype = defaultdict(lambda: defaultdict(lambda: Z))

    valuetypes = set()

    for deal in queryset:
        by_user[deal.owned_by].append(deal)

        month = deal.closed_on.replace(day=1)
        for value in deal.values.all():
            by_month_and_valuetype[month][value.type] += value.value
            valuetypes.add(value.type)

    deals = [
        {
            "user": user,
            "user_id": str(user.id),
            "deals": deals,
            "count": len(deals),
            "sum": sum(deal.value for deal in deals),
        }
        for user, deals in by_user.items()
    ]

    valuetypes = sorted(valuetypes)
    months = [
        {
            "month": month,
            "sum": sum(by_valuetype.values()),
            "values": [
                {"type": type, "value": by_valuetype.get(type, Z)}
                for type in valuetypes
            ],
        }
        for month, by_valuetype in by_month_and_valuetype.items()
    ]

    return {
        "by_user": sorted(deals, key=lambda row: row["sum"], reverse=True),
        "by_month_and_valuetype": sorted(months, key=lambda row: row["month"]),
        "by_valuetype": [
            {
                "type": type,
                "sum": sum(
                    by_valuetype[type]
                    for by_valuetype in by_month_and_valuetype.values()
                ),
            }
            for type in valuetypes
        ],
        "valuetypes": valuetypes,
        "sum": sum(row["sum"] for row in deals),
        "count": sum(row["count"] for row in deals),
    }


def test():  # pragma: no cover
    from pprint import pprint

    pprint(accepted_deals([dt.date(2020, 1, 1), dt.date(2020, 3, 31)]))
