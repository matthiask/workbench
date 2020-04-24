import datetime as dt
from collections import defaultdict

from django.db.models import Prefetch
from django.utils import timezone

from workbench.audit.models import LoggedAction
from workbench.deals.models import Deal, Value, ValueType
from workbench.tools.formats import Z2
from workbench.tools.history import EVERYTHING, changes


def accepted_deals(date_range, *, users=None):
    queryset = (
        Deal.objects.filter(status=Deal.ACCEPTED, closed_on__range=date_range)
        .select_related("customer", "contact__organization", "owned_by")
        .prefetch_related(
            Prefetch("values", queryset=Value.objects.select_related("type"))
        )
        .order_by("closed_on")
    )

    if users is not None:
        queryset = queryset.filter(owned_by__in=users)

    by_user = defaultdict(list)
    by_month_and_valuetype = defaultdict(lambda: defaultdict(lambda: Z2))

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

    valuetypes |= set(ValueType.objects.filter(weekly_target__isnull=False))
    valuetypes = sorted(valuetypes)
    months = [
        {
            "month": month,
            "sum": sum(by_valuetype.values()),
            "values": [
                {"type": type, "value": by_valuetype.get(type, Z2)}
                for type in valuetypes
            ],
        }
        for month, by_valuetype in by_month_and_valuetype.items()
    ]
    date_range_length = (date_range[1] - date_range[0]).days + 1

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
                "target": type.weekly_target * date_range_length / 7
                if type.weekly_target is not None
                else None,
            }
            for type in valuetypes
        ],
        "valuetypes": valuetypes,
        "sum": sum(row["sum"] for row in deals),
        "count": sum(row["count"] for row in deals),
        "target": sum(type.weekly_target or 0 for type in valuetypes)
        * date_range_length
        / 7,
        "weeks": date_range_length / 7,
    }


def declined_deals(date_range, *, users=None):
    queryset = (
        Deal.objects.filter(status=Deal.DECLINED, closed_on__range=date_range)
        .select_related("customer", "contact__organization", "owned_by")
        .prefetch_related(
            Prefetch("values", queryset=Value.objects.select_related("type"))
        )
        .order_by("-closed_on")
    )
    return queryset


def deal_history(date_range, *, users=None):
    actions = LoggedAction.objects.for_model(Deal).filter(
        created_at__range=[
            timezone.make_aware(dt.datetime.combine(day, time))
            for day, time in zip(date_range, [dt.time.min, dt.time.max])
        ]
    )
    fields = {
        "id",
        "title",
        "value",
        "probability",
        "decision_expected_on",
        "status",
        "closing_type",
        "closing_notice",
    }
    user_ids = EVERYTHING if users is None else {user.id for user in users} | {None}
    return [
        change
        for change in changes(Deal, fields, actions)
        if change.version.user_id in user_ids
    ]


def test():  # pragma: no cover
    from pprint import pprint

    pprint(accepted_deals([dt.date(2020, 1, 1), dt.date(2020, 3, 31)]))
