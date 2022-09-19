from django.db.models import Sum

from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost
from workbench.projects.models import Project, Service
from workbench.tools.formats import Z2


def playing_bank(projects):
    logged = {
        row["service__project"]: row["third_party_costs__sum"]
        for row in LoggedCost.objects.order_by()
        .filter(third_party_costs__isnull=False)
        .exclude(third_party_costs=0)
        .values("service__project")
        .annotate(Sum("third_party_costs"))
    }
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
        delta = row["logged"] - row["invoiced"]
        sums[delta > 0] += delta
        return row | {"delta": delta}

    projects = [
        _statsify(
            {
                "project": project,
                "offered": offered.get(project.id, Z2),
                "logged": logged.get(project.id, Z2),
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
