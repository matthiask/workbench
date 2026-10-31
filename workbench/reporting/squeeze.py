from collections import defaultdict
from decimal import Decimal
from itertools import chain

from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, NullIf
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.awt.reporting import employment_percentages
from workbench.awt.utils import monthly_days
from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.logbook.models import INVOICED_HOURS, LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import (
    BudgetTransfer,
    InternalType,
    InternalTypeUser,
    Project,
    Service,
)
from workbench.projects.reporting import hours_per_type
from workbench.reporting.utils import accepted_offers_by_project, sum_by, sum_of
from workbench.tools.formats import Z0, Z1, Z2, local_date_format
from workbench.tools.xlsx import WorkbenchXLSXDocument


BASE_HOURLY_RATE = Decimal(150)
WORKING_TIME_PER_DAY = Decimal(8)
WORKING_DAYS_PER_YEAR = Decimal(250)
DAYS_PER_YEAR = Decimal("365.24")


def working_days_estimation(date_range):
    days = (date_range[1] - date_range[0]).days + 1
    return days * WORKING_DAYS_PER_YEAR / DAYS_PER_YEAR


def relevant_hours(hours_offered, hours_logged, hours_logged_budgeted):
    """Hours logged on services which aren't budgeted (optional, declined,
    budget retainers) are added on top instead of disappearing in the max() so
    that we rather underestimate than overestimate the rate."""
    return (
        max(hours_offered, hours_logged_budgeted) + hours_logged - hours_logged_budgeted
    )


def third_party_costs_components(projects, *, until=None):
    """Third party costs on invoices and logged third party costs per project
    as two ``{project_id: amount}`` dicts, optionally only those invoiced or
    logged ``until`` a date.

    Final invoices contain the third party costs of down payments again, but
    down payments (e.g. of recurring invoices) may also be the only invoices,
    so the larger of both counts."""
    invoices = Invoice.objects.invoiced().filter(project__in=projects)
    logged_costs = LoggedCost.objects.filter(
        service__project__in=projects, third_party_costs__isnull=False
    )
    if until:
        invoices = invoices.filter(invoiced_on__lte=until)
        logged_costs = logged_costs.filter(rendered_on__lte=until)
    down_payments = sum_by(
        invoices.filter(type=Invoice.DOWN_PAYMENT),
        key="project",
        field="third_party_costs",
    )
    others = sum_by(
        invoices.exclude(type=Invoice.DOWN_PAYMENT),
        key="project",
        field="third_party_costs",
    )
    invoiced = defaultdict(
        lambda: Z2,
        {
            project: max(down_payments[project], others[project])
            for project in {*down_payments, *others}
        },
    )
    logged = sum_by(logged_costs, key="service__project", field="third_party_costs")
    return invoiced, logged


def third_party_costs(projects, *, until=None):
    """Third party costs per project as ``{project_id: amount}``.

    Logged costs are the actual costs, invoices know what has been passed on
    to the customer. Logged costs can't be linked to fixed amount invoices, and
    may be logged after a services invoice has been created from the offer, so
    adding up both would count many costs twice. Using the larger of the two
    still subtracts logged costs which haven't been invoiced yet."""
    invoiced, logged = third_party_costs_components(projects, until=until)
    return defaultdict(
        lambda: Z2,
        {
            project: max(invoiced[project], logged[project])
            for project in {*invoiced, *logged}
        },
    )


def gross_margin_components(projects, *, invoiced_until=None):
    """Offered, projected and invoiced gross margin per project as
    ``{project_id: {"offered": ..., "projected": ..., "invoiced": ...}}``.

    ``invoiced_until`` limits invoices and third party costs to a cutoff
    date. Offers and projections aren't versioned, they are always today's.

    Projections are only taken into account for open projects. Third party
    costs are deducted from offers and invoices."""
    accepted = accepted_offers_by_project(projects)
    offered = {project: row["total"] for project, row in accepted.items()}
    projected = sum_by(
        ProjectedInvoice.objects.filter(
            project__in=projects, project__closed_on__isnull=True
        ),
        key="project",
        field="gross_margin",
    )
    invoices = Invoice.objects.invoiced().filter(project__in=projects)
    if invoiced_until:
        invoices = invoices.filter(invoiced_on__lte=invoiced_until)
    invoiced = sum_by(invoices, key="project")
    invoiced_costs = third_party_costs(projects, until=invoiced_until)
    return defaultdict(
        lambda: {"offered": Z2, "projected": Z2, "invoiced": Z2},
        {
            project: {
                "offered": accepted[project]["total"]
                - accepted[project]["third_party_costs"],
                "projected": projected[project],
                "invoiced": invoiced[project] - invoiced_costs[project],
            }
            for project in {*offered, *projected, *invoiced, *invoiced_costs}
        },
    )


def hours_components(projects):
    """Offered (budgeted) and logged hours per project as
    ``{project_id: {"hours_offered": ..., "hours_logged": ...,
    "hours_logged_budgeted": ...}}``."""
    offered = sum_by(
        Service.objects.budgeted().filter(project__in=projects),
        key="project",
        field="service_hours",
        default=Z1,
    )
    logged = {
        row["service__project"]: row
        for row in LoggedHours.objects
        .filter(service__project__in=projects)
        .order_by()
        .values("service__project")
        .annotate(
            total=Sum("hours"),
            budgeted=Sum("hours", filter=Q(service__in=Service.objects.budgeted())),
        )
    }
    return defaultdict(
        lambda: {"hours_offered": Z1, "hours_logged": Z1, "hours_logged_budgeted": Z1},
        {
            project: {
                "hours_offered": offered[project],
                "hours_logged": logged[project]["total"] if project in logged else Z1,
                "hours_logged_budgeted": (
                    logged[project]["budgeted"] or Z1 if project in logged else Z1
                ),
            }
            for project in {*offered, *logged}
        },
    )


def project_gross_margin(project):
    """Compute the gross margin estimate and rate for a single project,
    using the same logic as the squeeze report."""
    # offered and hours_offered are needed for offered_rate even on closed
    # projects, projections are only available for open projects.
    gross_margins = gross_margin_components([project.id])[project.id]
    offered = gross_margins["offered"]
    projected = gross_margins["projected"]
    invoiced = gross_margins["invoiced"]
    accepted_offers = list(Offer.objects.accepted().filter(project=project))
    project_hours = hours_components([project.id])[project.id]
    hours_offered = project_hours["hours_offered"]
    hours_logged = project_hours["hours_logged"]
    hours_logged_budgeted = project_hours["hours_logged_budgeted"]
    # Only the hours of accepted offers match the offered amount (logged hours
    # are taken into account below).
    hours_accepted_offered = sum_of(
        Service.objects.budgeted().filter(offer__in=accepted_offers),
        field="service_hours",
        default=Z1,
    )

    # Including offered amounts and hours only makes sense for open projects;
    # for closed projects the invoiced amount and the logged hours are ground
    # truth.
    is_open = project.closed_on is None
    offered_for_margin = offered if is_open else Z2
    hours_offered_for_rate = hours_offered if is_open else Z1

    budgeted = Q(service__in=Service.objects.budgeted())
    accepted = Q(service__offer__in=accepted_offers)
    logged = LoggedHours.objects.filter(service__project=project).aggregate(
        accepted=Sum("hours", filter=accepted),
        accepted_budgeted=Sum("hours", filter=accepted & budgeted),
    )
    hours_accepted_logged = logged["accepted"] or Z1
    gross_margin = max(offered_for_margin, projected, invoiced)
    hours = relevant_hours(hours_offered_for_rate, hours_logged, hours_logged_budgeted)
    hours_accepted = relevant_hours(
        hours_accepted_offered,
        hours_accepted_logged,
        logged["accepted_budgeted"] or Z1,
    )

    # Budget which was invoiced here but is worked off elsewhere (or reserved
    # for that) has to follow the hours it paid for.
    budget_adjustment = BudgetTransfer.objects.adjustments(projects=[project])[
        project.id
    ]
    gross_margin = max(gross_margin + budget_adjustment, Z2)

    return {
        "gross_margin": gross_margin,
        "hours": hours,
        "hours_offered": hours_offered,
        "hours_logged": hours_logged,
        "hours_logged_budgeted": hours_logged_budgeted,
        "hours_logged_unbudgeted": hours_logged - hours_logged_budgeted,
        "hours_accepted": hours_accepted,
        "hours_accepted_offered": hours_accepted_offered,
        "hours_accepted_logged": hours_accepted_logged,
        "budget_adjustment": budget_adjustment,
        "rate": gross_margin / hours if hours else Z2,
        "offered_rate": offered / hours_accepted if hours_accepted else Z2,
        "offered": offered,
        "projected": projected,
        "invoiced": invoiced,
    }


def squeeze_data(date_range):  # noqa: C901
    projects = defaultdict(
        lambda: {
            "invoiced": Z2,
            "projected": Z2,
            "offered": Z2,
            "hours_logged": Z1,
            "hours_logged_budgeted": Z1,
            "hours_offered": Z1,
            "hours_in_range_by_user": {},
        }
    )
    users = defaultdict(
        lambda: {
            "gross_margin": Z2,
            "hours_in_range": Z1,
            "invoiced_hours_in_range": Z1,
            "by_project": {},
        }
    )
    user_dict = {u.id: u for u in User.objects.all()}

    # INVOICED_HOURS × COALESCE(effort_rate, default) is the value of the work.
    # A rate of 0.00 means the work is paid elsewhere (e.g. a package price),
    # not that it is worth nothing, so it gets the default rate too.
    _weighted_hours_expr = ExpressionWrapper(
        INVOICED_HOURS
        * Coalesce(
            NullIf(F("service__effort_rate"), Value(Z2)), Value(BASE_HOURLY_RATE)
        ),
        output_field=DecimalField(max_digits=14, decimal_places=4),
    )
    # Hours where no or a zero effort_rate was set (default rate was applied)
    _hours_rate_unknown_expr = Sum(
        Case(
            When(
                Q(service__effort_rate__isnull=True) | Q(service__effort_rate=0),
                then=F("hours"),
            ),
            default=Value(Decimal(0)),
            output_field=DecimalField(max_digits=10, decimal_places=1),
        )
    )

    logged = (
        LoggedHours.objects
        .filter(rendered_on__range=date_range)
        .order_by()
        .values("rendered_by", "service__project")
        .annotate(
            hours_sum=Sum("hours"),
            invoiced_hours_sum=Sum(INVOICED_HOURS),
            weighted_hours=Sum(_weighted_hours_expr),
            hours_rate_unknown=_hours_rate_unknown_expr,
        )
    )
    for row in logged:
        p = projects[row["service__project"]]
        u = user_dict[row["rendered_by"]]
        p["hours_in_range_by_user"][u] = {
            "hours": row["hours_sum"],
            "invoiced_hours": row["invoiced_hours_sum"],
            "weighted_hours": row["weighted_hours"],
            "hours_rate_unknown": row["hours_rate_unknown"] or Decimal(0),
        }
        users[u]["hours_in_range"] += row["hours_sum"]
        users[u]["invoiced_hours_in_range"] += row["invoiced_hours_sum"]

    # All-time hours (logged hours are the attribution denominator) and gross
    # margin. Offered amounts and hours only count for open projects.
    gross_margins = gross_margin_components(projects.keys())
    hours = hours_components(projects.keys())
    for project_id, project in (
        Project.objects.select_related("customer").in_bulk(projects.keys()).items()
    ):
        projects[project_id]["project"] = project
        projects[project_id] |= gross_margins[project_id] | hours[project_id]
        if project.closed_on is not None:
            projects[project_id]["offered"] = Z2
            projects[project_id]["hours_offered"] = Z1

    budget_adjustments = BudgetTransfer.objects.adjustments(projects=projects.keys())

    # Compute per-project margin, hours, rate, and per-user attribution
    project_list = []
    for p in projects.values():
        if "project" not in p:
            continue
        offered = p["offered"]
        projected = p["projected"]
        invoiced = p["invoiced"]
        margin = max((offered, projected, invoiced))
        hours_offered = p["hours_offered"]
        hours_logged = p["hours_logged"]
        hours = relevant_hours(hours_offered, hours_logged, p["hours_logged_budgeted"])

        # Budget which was invoiced here but is worked off elsewhere (or
        # reserved for that) has to follow the hours it paid for, otherwise the
        # source project pays too high a rate and the target project none.
        margin = max(margin + budget_adjustments[p["project"].id], Z2)

        # Total value of the work in the period across all users for this
        # project. Used to distribute the period slice between users.
        total_weighted_in_range = sum(
            d["weighted_hours"] for d in p["hours_in_range_by_user"].values()
        )
        hours_in_range_total = sum(
            d["hours"] for d in p["hours_in_range_by_user"].values()
        )
        # Period slice: same denominator as the old hours-only formula so that
        # the total attributed margin is unchanged; rate-weighting only affects
        # how that slice is divided between users.
        period_margin = hours_in_range_total / hours * margin if hours else Z2

        by_user = {}
        if total_weighted_in_range and hours:
            for u, user_data in p["hours_in_range_by_user"].items():
                user_hours = user_data["hours"]
                user_weighted = user_data["weighted_hours"]
                user_margin = user_weighted / total_weighted_in_range * period_margin
                contrib = {
                    "hours": user_hours,
                    "invoiced_hours": user_data["invoiced_hours"],
                    "gross_margin": user_margin,
                    "rate": user_margin / user_hours,
                    "hours_rate_unknown": user_data["hours_rate_unknown"],
                }
                users[u]["gross_margin"] += user_margin
                users[u]["by_project"][p["project"]] = contrib
                by_user[u] = contrib

        hours_in_range = sum(d["hours"] for d in by_user.values())
        invoiced_hours_in_range = sum(d["invoiced_hours"] for d in by_user.values())
        gross_margin_in_range = sum(d["gross_margin"] for d in by_user.values())
        hours_rate_unknown = sum(d["hours_rate_unknown"] for d in by_user.values())
        by_user = dict(
            sorted(by_user.items(), key=lambda item: item[1]["hours"], reverse=True)
        )

        project_list.append({
            "project": p["project"],
            "offered": offered,
            "projected": projected,
            "invoiced": invoiced,
            "gross_margin": margin,
            "hours_offered": hours_offered,
            "hours_logged": hours_logged,
            "hours": hours,
            "rate": margin / hours if hours else Z2,
            "by_user": by_user,
            "hours_in_range": hours_in_range,
            "invoiced_hours_in_range": invoiced_hours_in_range,
            "gross_margin_in_range": gross_margin_in_range,
            "hours_rate_unknown": hours_rate_unknown,
        })

    project_list.sort(key=lambda r: r["gross_margin_in_range"], reverse=True)

    all_users = sorted(users.keys())
    ep = employment_percentages()

    # Monthly percentages weighted with the days of the month in the period
    period_months = list(monthly_days(*date_range))
    period_days = sum(days for month, days in period_months)

    def average_percentage(user):
        return (
            sum((ep[user].get(month, Z0) * days for month, days in period_months), Z0)
            / period_days
        )

    hpt = hours_per_type(date_range, users=users.keys())
    hptu = {row["user"]: row for row in hpt["users"]}

    user_internal_types = defaultdict(dict)
    for m2m in InternalTypeUser.objects.select_related("internal_type"):
        user_internal_types[m2m.user_id][m2m.internal_type] = m2m
    types = list(InternalType.objects.all())

    absence_days_per_user = defaultdict(lambda: Z0)
    for absence in Absence.objects.filter(
        Q(ends_on__isnull=True, starts_on__range=date_range)
        | (
            Q(ends_on__isnull=False)
            & Q(starts_on__lte=date_range[1], ends_on__gte=date_range[0])
        ),
        Q(
            reason__in=[
                Absence.VACATION,
                Absence.PAID,
                Absence.SCHOOL,
            ]
        )
        | Q(
            reason=Absence.CORRECTION,
            days__gt=0,
        ),
    ).select_related("user"):
        # Spread the absence's days over its calendar days, count those in
        # the period
        ends_on = absence.ends_on or absence.starts_on
        overlap = (
            min(ends_on, date_range[1]) - max(absence.starts_on, date_range[0])
        ).days + 1
        absence_days_per_user[absence.user] += (
            absence.days * overlap / ((ends_on - absence.starts_on).days + 1)
        )

    # Build user dicts
    user_list = []
    for user, row in users.items():
        employment_percentage = average_percentage(user)
        hptu_row = hptu.get(user, {"internal": Z1, "external": Z1, "total": Z1})
        internal_hours = hptu_row["internal"]
        external_hours = hptu_row["external"]
        total_hours_user = hptu_row["total"]

        # internal_percentages: negative values e.g. -20 for 20% internal time
        internal_percentages = [
            -user_internal_types[user.id][type].percentage
            if type in user_internal_types[user.id]
            else 0
            for type in types
        ]
        profitable_percentage = 100 + sum(internal_percentages)
        external_percentage = (
            100 * external_hours / total_hours_user if total_hours_user else Z0
        )
        invoiced_per_external_hour = (
            row["gross_margin"]
            / row["hours_in_range"]
            / (1 - internal_hours / total_hours_user)
            if external_hours
            else Z2
        )
        absence_days = absence_days_per_user[user]

        if (
            user.specialist_field
            and user.specialist_field.expected_hourly_rate is not None
        ):
            expected_hourly_rate = user.specialist_field.expected_hourly_rate
        else:
            expected_hourly_rate = BASE_HOURLY_RATE

        expected_gross_margin = (
            expected_hourly_rate
            * WORKING_TIME_PER_DAY
            * (working_days_estimation(date_range) - absence_days)
            * Decimal(profitable_percentage)
            / 100
            * Decimal(employment_percentage)
            / 100
        )
        delta = row["gross_margin"] - expected_gross_margin

        # internal_type_percentages: list of (InternalType, negative_percentage_or_0)
        # where negative_percentage mirrors the internal_percentages list values
        internal_type_percentages = list(zip(types, internal_percentages))

        user_list.append({
            "user": user,
            "specialist_field": user.specialist_field.name
            if user.specialist_field
            else None,
            "employment_percentage": employment_percentage,
            "gross_margin": row["gross_margin"],
            "hours_in_range": row["hours_in_range"],
            "invoiced_hours_in_range": row["invoiced_hours_in_range"],
            "rate": row["gross_margin"] / row["hours_in_range"]
            if row["hours_in_range"]
            else Z2,
            "internal_hours": internal_hours,
            "external_hours": external_hours,
            "total_hours": total_hours_user,
            "invoiced_per_external_hour": invoiced_per_external_hour,
            "profitable_percentage": profitable_percentage,
            "external_percentage": external_percentage,
            "delta_external_percentage": external_percentage - profitable_percentage,
            "expected_hourly_rate": expected_hourly_rate,
            "expected_gross_margin": expected_gross_margin,
            "delta": delta,
            "absence_days": absence_days,
            "internal_type_percentages": internal_type_percentages,
            "by_project": dict(
                sorted(
                    row["by_project"].items(),
                    key=lambda item: item[1]["hours"],
                    reverse=True,
                )
            ),
            "hours_rate_unknown": sum(
                c["hours_rate_unknown"] for c in row["by_project"].values()
            ),
        })

    user_list.sort(key=lambda r: r["delta"], reverse=True)

    # Build specialist fields
    fields_dict = defaultdict(
        lambda: {
            "gross_margin": Z2,
            "hours_in_range": Z1,
            "external_hours": Z1,
            "total_hours": Z1,
            "names": [],
        }
    )
    for ud in user_list:
        field = ud["specialist_field"] or _("<unknown>")
        fields_dict[field]["gross_margin"] += ud["gross_margin"]
        fields_dict[field]["hours_in_range"] += ud["hours_in_range"]
        fields_dict[field]["external_hours"] += ud["external_hours"]
        fields_dict[field]["total_hours"] += ud["total_hours"]
        fields_dict[field]["names"].append(str(ud["user"]))

    field_list = sorted(
        [
            {
                "name": name,
                "users": ", ".join(sorted(d["names"])),
                "gross_margin": d["gross_margin"],
                "hours_in_range": d["hours_in_range"],
                "rate": d["gross_margin"] / d["hours_in_range"]
                if d["hours_in_range"]
                else Z2,
                "external_percentage": 100 * d["external_hours"] / d["total_hours"]
                if d["total_hours"]
                else Z2,
            }
            for name, d in fields_dict.items()
        ],
        key=lambda r: r["rate"],
        reverse=True,
    )

    # Build organizations
    organizations = defaultdict(lambda: {"gross_margin": Z2, "hours_in_range": Z1})
    for p in project_list:
        hours = p["hours"]
        if hours:
            org = p["project"].customer
            for u_data in p["by_user"].values():
                organizations[org]["gross_margin"] += u_data["gross_margin"]
                organizations[org]["hours_in_range"] += u_data["hours"]

    org_list = sorted(
        [
            {
                "organization": organization,
                "name": str(organization),
                "gross_margin": d["gross_margin"],
                "hours_in_range": d["hours_in_range"],
                "rate": d["gross_margin"] / d["hours_in_range"]
                if d["hours_in_range"]
                else Z2,
            }
            for organization, d in organizations.items()
        ],
        key=lambda r: r["rate"],
        reverse=True,
    )

    # Project totals
    project_totals = {
        "hours_in_range": sum(p["hours_in_range"] for p in project_list),
        "gross_margin_in_range": sum(p["gross_margin_in_range"] for p in project_list),
    }

    # Totals
    all_users_gross_margin = sum(ud["gross_margin"] for ud in user_list)
    all_users_hours_in_range = sum(ud["hours_in_range"] for ud in user_list)
    total_employment_percentage = sum(average_percentage(u) for u in all_users)
    total_internal = hpt["total"]["internal"]
    total_external = hpt["total"]["external"]
    total_total = hpt["total"]["total"]

    totals = {
        "employment_percentage": total_employment_percentage,
        "absence_days": sum(ud["absence_days"] for ud in user_list),
        "gross_margin": all_users_gross_margin,
        "hours_in_range": all_users_hours_in_range,
        "rate": all_users_gross_margin / all_users_hours_in_range
        if all_users_hours_in_range
        else Z2,
        "internal_hours": total_internal,
        "external_hours": total_external,
        "total_hours": total_total,
        "external_percentage": 100 * total_external / total_total
        if total_total
        else Z0,
        "invoiced_per_external_hour": (
            all_users_gross_margin
            / all_users_hours_in_range
            / (1 - total_internal / total_total)
            if total_external
            else Z2
        ),
        "expected_gross_margin": sum(ud["expected_gross_margin"] for ud in user_list),
        "delta": sum(ud["delta"] for ud in user_list),
    }

    return {
        "date_range": date_range,
        "projects": project_list,
        "project_totals": project_totals,
        "users": user_list,
        "fields": field_list,
        "organizations": org_list,
        "totals": totals,
        "all_users": all_users,
        "types": types,
        "default_hourly_rate": BASE_HOURLY_RATE,
    }


def build_xlsx(data):
    date_range = data["date_range"]
    all_users = data["all_users"]
    types = data["types"]
    user_list = data["users"]
    project_list = data["projects"]
    field_list = data["fields"]
    org_list = data["organizations"]
    totals = data["totals"]

    body = f"Squeeze {local_date_format(date_range[0])} - {local_date_format(date_range[1])}"
    header = [[body]]

    projects_table = [
        [
            _("project"),
            _("offered (only open projects)"),
            _("projected gross margin (only open projects)"),
            _("invoiced without third party costs"),
            _("gross margin (estimated)"),
            _("offered hours (only open projects)"),
            _("logged hours"),
            _("relevant hours"),
            _("rate"),
            _("period hours"),
            _("period invoiced hours"),
            _("period gross margin"),
            _("period rate"),
            _("hours at default rate ({}/h)").format(BASE_HOURLY_RATE),
            *list(chain.from_iterable((str(u), "", "", "", "") for u in all_users)),
        ],
        [
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            *list(
                chain.from_iterable(
                    (
                        _("hours"),
                        _("invoiced hours"),
                        _("gross margin"),
                        _("rate"),
                        _("hours at default rate"),
                    )
                    for _u in all_users
                )
            ),
        ],
        *sorted(
            (_project_xlsx_row(p, all_users) for p in project_list),
            key=lambda row: row[11],
            reverse=True,
        ),
    ]

    users_table = [
        [
            _("user"),
            _("specialist field"),
            _("employment percentage YTD"),
            _("included absence days"),
            _("relevant hours"),
            _("rate"),
            _("gross margin"),
            "",
            _("internal hours"),
            _("external hours"),
            _("total hours"),
            "",
            _("invoiced per external hour"),
            "",
            _("starting point"),
        ]
        + [type.name for type in types]
        + [
            _("Target value: external percentage"),
            _("external percentage"),
            "",
            _("expected hourly rate"),
            _("Target value: gross margin"),
            "",
            _("hours at default rate ({}/h)").format(BASE_HOURLY_RATE),
        ],
        [
            _("Total"),
            "",
            totals["employment_percentage"],
            "",
            totals["hours_in_range"],
            totals["rate"],
            totals["gross_margin"],
            "",
            totals["internal_hours"],
            totals["external_hours"],
            totals["total_hours"],
            "",
            totals["invoiced_per_external_hour"],
            "",
            "",
        ]
        + ["" for _type in types]
        + [
            "",
            totals["external_percentage"],
            _("Delta"),
            _("Target value w/ {}/h").format(BASE_HOURLY_RATE),
            _("Delta"),
            "",
        ],
        [],
        *sorted(
            (_user_xlsx_row(ud, types) for ud in user_list),
            key=lambda row: row[-2],
            reverse=True,
        ),
    ]

    fields_table = [
        [
            _("specialist field"),
            _("users"),
            _("relevant hours"),
            _("rate"),
            _("relevant gross margin"),
            _("external percentage"),
        ],
        *[
            [
                f["name"],
                f["users"],
                f["hours_in_range"],
                f["rate"],
                f["gross_margin"],
                f["external_percentage"],
            ]
            for f in field_list
        ],
    ]

    organizations_table = [
        [
            _("organization"),
            _("relevant gross margin"),
            _("relevant hours"),
            _("rate"),
        ],
        *[
            [
                o["name"],
                o["gross_margin"],
                o["hours_in_range"],
                o["rate"],
            ]
            for o in org_list
        ],
    ]

    xlsx = WorkbenchXLSXDocument()
    xlsx.add_sheet(_("projects"))
    xlsx.table(None, header + projects_table)
    xlsx.add_sheet(_("users").replace(":", "_"))
    xlsx.table(None, header + users_table)
    xlsx.add_sheet(_("specialist fields"))
    xlsx.table(None, header + fields_table)
    xlsx.add_sheet(_("organizations"))
    xlsx.table(None, header + organizations_table)

    return xlsx


def _project_xlsx_row(p, all_users):
    hours = p["hours"]
    hours_in_range = p["hours_in_range"]

    def user_cells(u):
        if d := p["by_user"].get(u):
            return (
                d["hours"],
                d["invoiced_hours"],
                d["gross_margin"],
                d["rate"],
                d["hours_rate_unknown"] or "",
            )
        return ("", "", "", "", "")

    return [
        p["project"],
        p["offered"],
        p["projected"],
        p["invoiced"],
        p["gross_margin"],
        p["hours_offered"],
        p["hours_logged"],
        hours,
        p["rate"],
        hours_in_range,
        p["invoiced_hours_in_range"],
        p["gross_margin_in_range"],
        p["gross_margin_in_range"] / hours_in_range if hours_in_range else "",
        p["hours_rate_unknown"] or "",
        *list(chain.from_iterable(user_cells(u) for u in all_users)),
    ]


def _user_xlsx_row(ud, types):
    user = ud["user"]
    # internal_type_percentages contains (type, negative_pct_or_0) pairs
    # Convert 0 to None to match original behaviour: [p or None for p in internal_percentages]
    internal_percentages_list = [
        pct or None for _t, pct in ud["internal_type_percentages"]
    ]
    return [
        user,
        ud["specialist_field"] or _("<unknown>"),
        ud["employment_percentage"],
        ud["absence_days"],
        ud["hours_in_range"],
        ud["rate"],
        ud["gross_margin"],
        "",
        ud["internal_hours"],
        ud["external_hours"],
        ud["total_hours"],
        "",
        ud["invoiced_per_external_hour"],
        "",
        100,
        *internal_percentages_list,
        ud["profitable_percentage"],
        ud["external_percentage"],
        ud["external_percentage"] - ud["profitable_percentage"],
        ud["expected_hourly_rate"],
        ud["expected_gross_margin"],
        ud["delta"],
        ud["hours_rate_unknown"] or "",
    ]
