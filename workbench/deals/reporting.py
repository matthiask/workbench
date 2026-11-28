import datetime as dt
from collections import defaultdict
from itertools import chain

from django.db.models import Prefetch
from django.utils import timezone

from workbench.audit.models import LoggedAction
from workbench.deals.models import Contribution, Deal, Value, ValueType
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.formats import Z2
from workbench.tools.history import EVERYTHING, changes


def accepted_deals(date_range, *, users=None):
    queryset = (
        Deal.objects
        .filter(status=Deal.ACCEPTED, closed_on__range=date_range)
        .select_related("customer", "contact__organization", "owned_by")
        .prefetch_related(
            Prefetch(
                "contributions", queryset=Contribution.objects.select_related("user")
            ),
            Prefetch("values", queryset=Value.objects.select_related("type")),
        )
        .order_by("closed_on")
    )

    # Accepted offers without deal, e.g. follow-up orders, count as won too,
    # so do those whose deals have all been declined (else they'd count
    # nowhere)
    offers = (
        Offer.objects
        .accepted()
        .filter(closed_on__range=date_range)
        .exclude(deals__status__in=[Deal.OPEN, Deal.ACCEPTED])
        .exclude(project__type=Project.INTERNAL)
        .select_related("owned_by", "project__customer")
        .prefetch_related("services")
        .order_by("closed_on", "pk")
    )

    # Maintenance sold without deal and without offer, e.g. ongoing work for
    # existing customers: what was invoiced in the period, credited to the
    # project owner. Linking the project (or an offer of it) to a deal says
    # the deal covers it.
    maintenance = (
        Invoice.objects
        .invoiced()
        .filter(
            invoiced_on__range=date_range,
            project__in=Project.objects
            .filter(type=Project.MAINTENANCE)
            .exclude(offers__status=Offer.ACCEPTED)
            .exclude(deals__isnull=False)
            .exclude(offers__deals__isnull=False),
        )
        .select_related("project__owned_by", "project__customer")
        .order_by("invoiced_on", "pk")
    )

    if users is not None:
        queryset = queryset.filter(owned_by__in=users)
        offers = offers.filter(owned_by__in=users)
        maintenance = maintenance.filter(project__owned_by__in=users)

    by_user = defaultdict(dict)
    offers_by_user = defaultdict(dict)
    offers_by_month = defaultdict(lambda: Z2)
    maintenance_by_user = defaultdict(lambda: defaultdict(lambda: Z2))
    maintenance_by_month = defaultdict(lambda: Z2)
    maintenance_by_project = {}
    by_month_and_valuetype = defaultdict(lambda: defaultdict(lambda: Z2))
    age_by_valuetype = defaultdict(list)

    valuetypes = set()

    for deal in queryset:
        contributions = deal.contributions.all()
        weight = sum((c.weight for c in contributions), 0)
        for c in contributions:
            by_user[c.user][deal] = deal.value * c.weight / weight if weight else Z2

        month = deal.closed_on.replace(day=1)
        for value in deal.values.all():
            by_month_and_valuetype[month][value.type] += value.value
            valuetypes.add(value.type)

            age_by_valuetype[value.type].append(
                (deal.closed_on - deal.created_at.date()).days
            )

    # Third party costs aren't won business, deals don't contain them either
    for offer in offers:
        won = offer.gross_margin
        offers_by_user[offer.owned_by][offer] = won
        offers_by_month[offer.closed_on.replace(day=1)] += won

    for invoice in maintenance:
        project = invoice.project
        maintenance_by_user[project.owned_by][project] += Z2
        row = maintenance_by_project.setdefault(
            project, {"project": project, "sum": Z2, "invoices": []}
        )
        row["invoices"].append(invoice)

    # Final invoices repeat the third party costs of their down payments,
    # deduct them once like the projects' invoiced gross margin: the growth
    # of gross_margin_components() from month end to month end
    for cutoff, before, after in maintenance_gross_margin(
        maintenance_by_project, date_range
    ):
        for project, row in maintenance_by_project.items():
            won = after[project.pk]["invoiced"] - before[project.pk]["invoiced"]
            if won:
                maintenance_by_user[project.owned_by][project] += won
                maintenance_by_month[cutoff.replace(day=1)] += won
                row["sum"] += won

    def user_row(user):
        user_deals = by_user.get(user, {})
        user_offers = offers_by_user.get(user, {})
        user_maintenance = dict(maintenance_by_user.get(user, {}))
        return {
            "user": user,
            "user_id": str(user.id),
            "deals": user_deals,
            "offers": user_offers,
            "maintenance": user_maintenance,
            "count": len(user_deals) + len(user_offers) + len(user_maintenance),
            "sum": sum(user_deals.values(), Z2)
            + sum(user_offers.values(), Z2)
            + sum(user_maintenance.values(), Z2),
        }

    deals = [
        user_row(user)
        for user in by_user.keys() | offers_by_user.keys() | maintenance_by_user.keys()
    ]

    valuetypes |= set(ValueType.objects.filter(weekly_target__isnull=False))
    valuetypes = sorted(valuetypes)
    months = [
        {
            "month": month,
            "sum": sum(by_month_and_valuetype[month].values(), Z2)
            + offers_by_month[month]
            + maintenance_by_month[month],
            "values": [
                {"type": type, "value": by_month_and_valuetype[month].get(type, Z2)}
                for type in valuetypes
            ],
            "offers": offers_by_month[month],
            "maintenance": maintenance_by_month[month],
        }
        for month in by_month_and_valuetype.keys()
        | offers_by_month.keys()
        | maintenance_by_month.keys()
    ]
    date_range_length = (date_range[1] - date_range[0]).days + 1

    def median(iterable):
        lst = sorted(iterable)
        if not lst:
            return None
        return lst[len(lst) // 2]

    median_age_by_valuetype = {
        valuetype: median(ages) for valuetype, ages in age_by_valuetype.items()
    }

    return {
        "deals": queryset,
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
                "median_age": median_age_by_valuetype.get(type),
            }
            for type in valuetypes
        ],
        "valuetypes": valuetypes,
        "offers": offers,
        "offers_sum": sum(offers_by_month.values(), Z2),
        "maintenance": sorted(
            maintenance_by_project.values(), key=lambda row: row["project"].code
        ),
        "maintenance_sum": sum(maintenance_by_month.values(), Z2),
        # Deals may have several or no contributors
        "sum": sum((deal.value for deal in queryset), Z2)
        + sum(offers_by_month.values(), Z2)
        + sum(maintenance_by_month.values(), Z2),
        "count": len(queryset) + len(offers) + len(maintenance_by_project),
        "target": sum(type.weekly_target or 0 for type in valuetypes)
        * date_range_length
        / 7,
        "weeks": date_range_length / 7,
        "median_age": median(chain.from_iterable(age_by_valuetype.values())),
    }


def maintenance_gross_margin(projects, date_range):
    """The invoiced gross margin of the projects at the end of each month of
    the date range as ``(month_end, before, after)`` triples, ``before`` is
    the gross margin at the previous month's end (or the range's start)"""
    from workbench.reporting.squeeze import gross_margin_components

    if not projects:
        return []
    project_ids = [project.pk for project in projects]
    cutoffs = [date_range[0] - dt.timedelta(days=1)]
    month = date_range[0].replace(day=1)
    while month <= date_range[1]:
        next_month = (month + dt.timedelta(days=31)).replace(day=1)
        cutoffs.append(min(next_month - dt.timedelta(days=1), date_range[1]))
        month = next_month
    margins = [
        gross_margin_components(project_ids, invoiced_until=cutoff)
        for cutoff in cutoffs
    ]
    return list(zip(cutoffs[1:], margins[:-1], margins[1:], strict=True))


def declined_deals(date_range, *, users=None):
    return (
        Deal.objects
        .filter(status=Deal.DECLINED, closed_on__range=date_range)
        .select_related("customer", "contact__organization", "owned_by")
        .prefetch_related(
            Prefetch("values", queryset=Value.objects.select_related("type"))
        )
        .order_by("-closed_on")
    )


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
