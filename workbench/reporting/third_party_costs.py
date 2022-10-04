import datetime as dt
from collections import defaultdict

from django.db.models import Sum

from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost
from workbench.projects.models import Project, Service
from workbench.tools.formats import Z2


def playing_bank(projects):
    logged = defaultdict(lambda: {"past": Z2, "future": Z2})
    for row in (
        LoggedCost.objects.order_by()
        .extra(select={"_is_future": f"rendered_on > '{dt.date.today().isoformat()}'"})
        .filter(third_party_costs__isnull=False)
        .exclude(third_party_costs=0)
        .values("service__project", "_is_future")
        .annotate(Sum("third_party_costs"))
    ):
        logged[row["service__project"]][
            "future" if row["_is_future"] else "past"
        ] += row["third_party_costs__sum"]

    invoiced = {
        row["project"]: row["third_party_costs__sum"]
        for row in Invoice.objects.invoiced()
        .order_by()
        .filter(project__isnull=False)
        .exclude(third_party_costs=0)
        .values("project")
        .annotate(Sum("third_party_costs"))
    }
    offered = {
        row["project"]: row["third_party_costs__sum"]
        for row in Service.objects.order_by()
        .filter(third_party_costs__isnull=False)
        .exclude(third_party_costs=0)
        .values("project")
        .annotate(Sum("third_party_costs"))
    }

    sums = {True: Z2, False: Z2}

    def _statsify(row):
        delta = sum(row["logged"].values(), Z2) - row["invoiced"]
        sums[delta > 0] += delta
        return row | {"delta": delta}

    projects = [
        _statsify(
            {
                "project": project,
                "offered": offered.get(project.id, Z2),
                "logged": logged[project.id],
                "invoiced": invoiced.get(project.id, Z2),
            }
        )
        for project in projects.filter(
            id__in=offered.keys() | logged.keys() | invoiced.keys()
        )
    ]

    return {
        "projects": sorted(projects, key=lambda row: row["delta"]),
        "total_plus": sums[True],
        "total_minus": sums[False],
        "total_offered": sum(row["offered"] for row in projects),
        "total_logged": {
            "past": sum(row["logged"]["past"] for row in projects),
            "future": sum(row["logged"]["future"] for row in projects),
        },
        "total_invoiced": sum(row["invoiced"] for row in projects),
    }


def test():  # pragma: no cover
    import datetime as dt
    from pprint import pprint

    from django.db.models import Q

    pprint(
        playing_bank(
            projects=Project.objects.filter(
                Q(closed_on__isnull=True) | Q(closed_on__gt=dt.date(2022, 1, 1))
            )
        )
    )
