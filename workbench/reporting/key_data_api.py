import datetime as dt
import secrets
from collections import defaultdict

from django.conf import settings
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from workbench.awt.reporting import full_time_equivalents_by_month
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice
from workbench.reporting import key_data, squeeze
from workbench.reporting.green_hours import green_hours_by_month
from workbench.reporting.models import Accruals
from workbench.templatetags.workbench import deal_group
from workbench.tools.formats import Z1, Z2


def open_invoices_total(cutoff_date):
    return (
        Invoice.objects
        .invoiced()
        .filter(
            Q(invoiced_on__lte=cutoff_date),
            Q(closed_on__gt=cutoff_date) | Q(closed_on__isnull=True),
        )
        .order_by()
        .aggregate(t=Sum("total_excl_tax"))["t"]
        or Z2
    )


def canceled_invoices_total(date_range):
    return (
        Invoice.objects
        .filter(status=Invoice.CANCELED, closed_on__range=date_range)
        .order_by()
        .aggregate(t=Sum("total_excl_tax"))["t"]
        or Z2
    )


def accruals(cutoff_date):
    if obj := Accruals.objects.filter(cutoff_date=cutoff_date).first():
        return obj.accruals
    return Accruals.objects.accruals(cutoff_date=cutoff_date)


def deals_funnel():
    funnel = defaultdict(lambda: Z2)
    for deal in Deal.objects.filter(status=Deal.OPEN):
        if deal.probability == Deal.HIGH:
            key = {
                1: "high_probability_next_4_weeks",
                2: "high_probability_next_12_weeks",
                3: "high_probability_later",
            }[deal_group(deal)[0]]
        elif deal.probability == Deal.NORMAL:
            key = "normal_probability"
        else:
            continue
        funnel[key] += deal.value
    return {
        key: funnel[key]
        for key in [
            "high_probability_next_4_weeks",
            "high_probability_next_12_weeks",
            "high_probability_later",
            "normal_probability",
        ]
    }


def accepted_deals(date_range):
    return [
        {
            "id": deal.id,
            "title": deal.title,
            "customer": deal.customer.name,
            "value": deal.value,
            "closed_on": deal.closed_on,
        }
        for deal in Deal.objects
        .filter(status=Deal.ACCEPTED, closed_on__range=date_range)
        .select_related("customer")
        .order_by("closed_on", "id")
    ]


def key_data_for_month(first_of_month):
    last_of_month = (first_of_month + dt.timedelta(days=31)).replace(
        day=1
    ) - dt.timedelta(days=1)
    date_range = [first_of_month, last_of_month]
    month = (first_of_month.year, first_of_month.month)

    gross_margin = next(
        (
            row["gross_margin"]
            for row in key_data.gross_margin_by_month(date_range)
            if row["month"] == month
        ),
        Z2,
    )
    green_hours = {row["month"]: row["percentage"] for row in green_hours_by_month()}
    previous_months = []
    day = first_of_month
    for _i in range(3):
        day = (day - dt.timedelta(days=1)).replace(day=1)
        previous_months.append({
            "month": f"{day:%Y-%m}",
            "green_hours_percentage": green_hours.get(day),
        })

    return {
        "month": f"{first_of_month:%Y-%m}",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "green_hours_percentage": green_hours.get(first_of_month),
        "previous_months": previous_months,
        "gross_margin": gross_margin,
        "open_invoices_total_excl_tax": open_invoices_total(last_of_month),
        "canceled_invoices_total_excl_tax": canceled_invoices_total(date_range),
        "accruals": accruals(last_of_month),
        "full_time_equivalents": full_time_equivalents_by_month().get(
            first_of_month, Z1
        ),
        "squeeze_gross_margin": squeeze.squeeze_data(date_range)["totals"][
            "gross_margin"
        ],
        "deals_funnel": deals_funnel(),
        "accepted_deals": accepted_deals(date_range),
    }


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dt.date):
        return value.isoformat()
    if value is None or isinstance(value, (str, int)):
        return value
    return float(value)


@require_GET
def key_data_api(request):
    token = settings.KEY_DATA_API_TOKEN
    if not token or not secrets.compare_digest(
        request.headers.get("Authorization", ""), f"Bearer {token}"
    ):
        return HttpResponseForbidden()

    previous_month = (dt.date.today().replace(day=1) - dt.timedelta(days=1)).replace(
        day=1
    )
    return JsonResponse(_jsonable(key_data_for_month(previous_month)))
