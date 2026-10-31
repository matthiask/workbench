from decimal import Decimal

from django.utils.formats import date_format
from django.utils.translation import gettext as _, gettext_lazy

from workbench.tools.charts import bar_chart
from workbench.tools.formats import Z1, hours


#: The limit of the running balance in the employment contracts, independent
#: of the pensum. Not applied strictly, so it's only a hint in the report.
BALANCE_LIMIT = Decimal(40)


def balance_chart(weeks, *, as_of):
    """The running balance per week with the weekly balance as bars

    Weeks after ``as_of`` (the end of the last completed month) are drawn
    lighter since their hours may not have been logged yet."""
    if not weeks:
        return None

    def split(*, complete):
        return [
            row["delta"] if (as_of is None or row["week"] <= as_of) == complete else 0
            for row in weeks
        ]

    return bar_chart(
        [f"KW{row['week']:%V}" for row in weeks],
        bars=[
            {
                "label": _("Balance per week"),
                "values": split(complete=True),
                "color": "wb-series-1",
            },
            {
                "label": _("Balance per week (current month)"),
                "values": split(complete=False),
                "color": "wb-series-projected",
            },
        ],
        lines=[
            {
                "label": _("Running balance"),
                "values": [row["running_delta"] for row in weeks],
                "color": "wb-series-7",
            },
            *(
                {
                    "label": label,
                    "values": [limit] * len(weeks),
                    "color": "wb-series-muted",
                    "dashed": True,
                }
                for label, limit in [
                    (
                        _("Limit (%s)") % hours(BALANCE_LIMIT, plus_sign=True),
                        BALANCE_LIMIT,
                    ),
                    ("", -BALANCE_LIMIT),
                ]
            ),
        ],
        fmt=hours,
    )


ABSENCE_SERIES = [
    ("absence_vacation", gettext_lazy("vacation"), "wb-series-3"),
    ("absence_sickness", gettext_lazy("sickness"), "wb-series-2"),
    ("absence_paid", gettext_lazy("Paid leave"), "wb-series-4"),
    ("absence_school", gettext_lazy("School attendance of apprentices"), "wb-series-5"),
    ("absence_correction", gettext_lazy("Working time correction"), "wb-series-8"),
]


def working_time_chart(row):
    """Logged hours and countable absences per month compared to the target"""
    months = row["months"]
    per_day = months["year"].working_time_per_day

    def absence_hours(field):
        values = months[field]
        if field == "absence_vacation":
            # Vacation beyond the entitlement doesn't count as working time
            values = [
                days + correction
                for days, correction in zip(
                    values, months["vacation_days_correction"], strict=True
                )
            ]
        return [days * per_day for days in values]

    absences = [
        {"label": label, "values": absence_hours(field), "color": color}
        for field, label, color in ABSENCE_SERIES
    ]
    return bar_chart(
        [date_format(month, "M") for month in months["months"]],
        bars=[
            {
                "label": _("logged hours"),
                "values": months["hours"],
                "color": "wb-series-1",
            },
            *(series for series in absences if any(series["values"])),
        ],
        lines=[
            {
                "label": _("target time"),
                "values": months["target"],
                "color": "wb-series-muted",
            }
        ],
        fmt=hours,
    )


def vacation_meter(totals):
    """Taken, planned and left vacation days as percentages of a bar

    Vacation beyond the available days is shown as excess."""
    available = max(totals["available_vacation_days"], Z1)
    taken = totals["vacation_days_taken"]
    planned = totals["vacation_days_planned"]
    scale = max(available, taken + planned)
    if not scale:
        return None

    def percent(value):
        return f"{100 * max(value, 0) / scale:.2f}"

    excess = max(taken + planned - available, Z1)
    # The excess is shown on top of the taken and planned days, which
    # therefore only fill the bar up to the available days.
    planned_within = max(min(planned, available - taken), 0)
    return {
        "taken": percent(min(taken, available)),
        "planned": percent(planned_within),
        "excess": percent(excess),
        "excess_days": excess,
    }
