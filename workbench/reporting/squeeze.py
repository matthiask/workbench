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
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.awt.models import Absence
from workbench.awt.reporting import employment_percentages
from workbench.awt.utils import monthly_days
from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.invoices.utils import recurring
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import InternalType, InternalTypeUser, Project, Service
from workbench.projects.reporting import hours_per_type
from workbench.tools.formats import Z0, Z1, Z2, local_date_format
from workbench.tools.xlsx import WorkbenchXLSXDocument


EXPECTED_AVERAGE_HOURLY_RATE = Decimal(150)
WORKING_TIME_PER_DAY = Decimal(8)
WORKING_DAYS_PER_YEAR = Decimal(250)
DAYS_PER_YEAR = Decimal("365.24")


def working_days_estimation(date_range):
    days = (date_range[1] - date_range[0]).days + 1
    return days * WORKING_DAYS_PER_YEAR / DAYS_PER_YEAR


def project_gross_margin(project):
    """Compute the gross margin estimate and rate for a single project,
    using the same logic as the squeeze report."""
    invoiced_agg = (
        Invoice.objects
        .invoiced()
        .filter(project=project)
        .aggregate(Sum("total_excl_tax"), Sum("third_party_costs"))
    )
    invoiced = (invoiced_agg["total_excl_tax__sum"] or Z2) - (
        invoiced_agg["third_party_costs__sum"] or Z2
    )
    invoiced -= (
        LoggedCost.objects.filter(
            service__project=project,
            third_party_costs__isnull=False,
            invoice_service__isnull=True,
        ).aggregate(s=Sum("third_party_costs"))["s"]
        or Z2
    )

    # Always compute offered/hours_offered — needed for offered_rate even on closed projects.
    accepted_offers = list(Offer.objects.accepted().filter(project=project))
    offered = sum((o.total_excl_tax for o in accepted_offers), Z2)
    offered -= (
        Service.objects.filter(
            offer__in=accepted_offers, third_party_costs__isnull=False
        ).aggregate(s=Sum("third_party_costs"))["s"]
        or Z2
    )
    hours_offered = (
        Service.objects
        .budgeted()
        .filter(project=project)
        .aggregate(s=Sum("service_hours"))["s"]
        or Z1
    )

    # Projected invoices and including offered in gross_margin only makes sense
    # for open projects; for closed projects the invoiced amount is ground truth.
    projected = Z2
    offered_for_margin = Z2
    if project.closed_on is None:
        projected = sum(
            (
                pi.gross_margin
                for pi in ProjectedInvoice.objects.filter(project=project)
            ),
            Z2,
        )
        offered_for_margin = offered

    hours_logged = (
        LoggedHours.objects.filter(service__project=project).aggregate(s=Sum("hours"))[
            "s"
        ]
        or Z1
    )
    gross_margin = max(offered_for_margin, projected, invoiced)
    hours = max(hours_offered, hours_logged)
    return {
        "gross_margin": gross_margin,
        "hours": hours,
        "hours_offered": hours_offered,
        "hours_logged": hours_logged,
        "rate": gross_margin / hours if hours else Z2,
        "offered_rate": offered / hours_offered if hours_offered else Z2,
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
            "hours_offered": Z1,
            "hours_in_range_by_user": {},
        }
    )
    users = defaultdict(
        lambda: {
            "gross_margin": Z2,
            "hours_in_range": Z1,
            "by_project": {},
        }
    )
    user_dict = {u.id: u for u in User.objects.all()}

    # hours × COALESCE(effort_rate, default) gives a rate-weighted hours value
    _weighted_hours_expr = ExpressionWrapper(
        F("hours")
        * Coalesce(F("service__effort_rate"), Value(EXPECTED_AVERAGE_HOURLY_RATE)),
        output_field=DecimalField(max_digits=14, decimal_places=4),
    )
    # Hours where no effort_rate was set (default rate was applied)
    _hours_rate_unknown_expr = Sum(
        Case(
            When(service__effort_rate__isnull=True, then=F("hours")),
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
            weighted_hours=Sum(_weighted_hours_expr),
            hours_rate_unknown=_hours_rate_unknown_expr,
        )
    )
    for row in logged:
        p = projects[row["service__project"]]
        u = user_dict[row["rendered_by"]]
        p["hours_in_range_by_user"][u] = {
            "hours": row["hours_sum"],
            "weighted_hours": row["weighted_hours"],
            "hours_rate_unknown": row["hours_rate_unknown"] or Decimal(0),
        }
        users[u]["hours_in_range"] += row["hours_sum"]

    # Total all-time logged hours per project (used as attribution denominator)
    total_hours = (
        LoggedHours.objects
        .order_by()
        .filter(service__project__in=projects.keys())
        .values("service__project")
        .annotate(hours__sum=Sum("hours"))
    )
    for row in total_hours:
        projects[row["service__project"]]["hours_logged"] = row["hours__sum"]

    offered_hours = (
        Service.objects
        .order_by()
        .budgeted()
        .filter(project__in=projects.keys(), project__closed_on__isnull=True)
        .values("project")
        .annotate(Sum("service_hours"))
    )
    for row in offered_hours:
        projects[row["project"]]["hours_offered"] = row["service_hours__sum"]

    invoiced_per_project = (
        Invoice.objects
        .invoiced()
        .filter(project__in=projects.keys())
        .order_by()
        .values("project")
        .annotate(Sum("total_excl_tax"), Sum("third_party_costs"))
    )
    for row in invoiced_per_project:
        projects[row["project"]]["invoiced"] = (
            row["total_excl_tax__sum"] - row["third_party_costs__sum"]
        )

    # Subtract third party costs from logged costs which have not been
    # invoiced yet. Maybe we're double counting here but I'd rather have a
    # pessimistic outlook here.
    for row in (
        LoggedCost.objects
        .filter(
            service__project__in=projects.keys(),
            third_party_costs__isnull=False,
            invoice_service__isnull=True,
        )
        .order_by()
        .values("service__project")
        .annotate(Sum("third_party_costs"))
    ):
        projects[row["service__project"]]["invoiced"] -= row["third_party_costs__sum"]

    for pi in ProjectedInvoice.objects.filter(
        project__in=projects.keys(), project__closed_on__isnull=True
    ):
        projects[pi.project_id]["projected"] += pi.gross_margin

    offers = Offer.objects.accepted().filter(
        project__in=projects.keys(), project__closed_on__isnull=True
    )
    for offer in offers:
        projects[offer.project_id]["offered"] += offer.total_excl_tax
    for row in (
        Service.objects
        .filter(offer__in=offers, third_party_costs__isnull=False)
        .order_by()
        .values("project")
        .annotate(Sum("third_party_costs"))
    ):
        projects[row["project"]]["offered"] -= row["third_party_costs__sum"]

    for project_id, project in Project.objects.in_bulk(projects.keys()).items():
        projects[project_id]["project"] = project

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
        hours = max((hours_offered, hours_logged))

        # Total weighted hours in the period across all users for this project.
        # Used to distribute the period slice between users by rate-weighted hours.
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
                    "gross_margin": user_margin,
                    "rate": user_margin / user_hours,
                    "hours_rate_unknown": user_data["hours_rate_unknown"],
                }
                users[u]["gross_margin"] += user_margin
                users[u]["by_project"][p["project"]] = contrib
                by_user[u] = contrib

        hours_in_range = sum(d["hours"] for d in by_user.values())
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
            "gross_margin_in_range": gross_margin_in_range,
            "hours_rate_unknown": hours_rate_unknown,
        })

    project_list.sort(key=lambda r: r["gross_margin_in_range"], reverse=True)

    all_users = sorted(users.keys())
    ep = employment_percentages()

    def average_percentage(user):
        percentages = []
        for month in recurring(date_range[0], "monthly"):
            if month > date_range[1]:
                break
            percentages.append(ep[user].get(month, Z0))
        return sum(percentages, Z0) / len(percentages)

    hpt = hours_per_type(date_range, users=users.keys())
    hptu = {row["user"]: row for row in hpt["users"]}

    user_internal_types = defaultdict(dict)
    for m2m in InternalTypeUser.objects.select_related("internal_type"):
        user_internal_types[m2m.user_id][m2m.internal_type] = m2m
    types = list(InternalType.objects.all())

    absence_days_per_user = defaultdict(lambda: Decimal(1))
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
        months = list(
            monthly_days(absence.starts_on, absence.ends_on or absence.starts_on)
        )
        absence_day_per_period_day = absence.days / sum(m[1] for m in months)
        for month, days in months:
            if date_range[0] <= month <= date_range[1]:
                absence_days_per_user[absence.user] += days * absence_day_per_period_day

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
            expected_hourly_rate = EXPECTED_AVERAGE_HOURLY_RATE

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
        field = ud["specialist_field"] or "<unbekannt>"
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
        "default_hourly_rate": EXPECTED_AVERAGE_HOURLY_RATE,
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
            _("period gross margin"),
            _("period rate"),
            _("hours at default rate ({}/h)").format(EXPECTED_AVERAGE_HOURLY_RATE),
            *list(chain.from_iterable((str(u), "", "", "") for u in all_users)),
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
            *list(
                chain.from_iterable(
                    (
                        _("hours"),
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
            key=lambda row: row[10],
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
            _("hours at default rate ({}/h)").format(EXPECTED_AVERAGE_HOURLY_RATE),
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
            _("Target value w/ {}/h").format(EXPECTED_AVERAGE_HOURLY_RATE),
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
                d["gross_margin"],
                d["rate"],
                d["hours_rate_unknown"] or "",
            )
        return ("", "", "", "")

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
