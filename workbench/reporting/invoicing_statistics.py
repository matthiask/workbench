from datetime import date

from django.db.models import Sum

from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost
from workbench.tools.models import Z


def monthly_invoicing(year):
    invoices = Invoice.objects.filter(invoiced_on__year=year).valid()

    overall = {"total": Z, "total_excl_tax": Z, "third_party_costs": Z, "months": []}

    def add_month(month):
        overall["total"] += month["total"]
        overall["total_excl_tax"] += month["total_excl_tax"]
        overall["third_party_costs"] += month["third_party_costs"]
        overall["months"].append(month.copy())

    third_party_costs_by_project = {
        row["service__project"]: row["third_party_costs__sum"]
        for row in LoggedCost.objects.order_by()
        .filter(service__project__in=invoices.values("project"))
        .values("service__project")
        .annotate(Sum("third_party_costs"))
    }

    month_data = {"total": Z, "total_excl_tax": Z, "third_party_costs": Z}
    month = dict(month_data, month=date(year, 1, 1), invoices=[])

    for invoice in invoices.select_related(
        "customer", "contact__organization", "project__owned_by", "owned_by"
    ).order_by("invoiced_on"):

        if month["month"].month != invoice.invoiced_on.month:
            add_month(month)
            month.update(month_data)
            month.update({"month": invoice.invoiced_on, "invoices": []})

        # FIXME double counting
        third_party_costs = third_party_costs_by_project.get(invoice.project_id, Z)

        month["total"] += invoice.total
        month["total_excl_tax"] += invoice.total_excl_tax
        month["third_party_costs"] += third_party_costs
        month["invoices"].append(invoice)

    if month["invoices"]:
        add_month(month)

    return overall
