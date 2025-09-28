import datetime as dt
import io
from collections import defaultdict
from pprint import pprint

from django.core.mail import EmailMultiAlternatives
from django.core.management import BaseCommand
from django.db.models import Sum

from workbench.deals.models import Deal, ValueType
from workbench.invoices.models import Invoice, ProjectedInvoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.models import Project
from workbench.tools.formats import Z1, Z2
from workbench.tools.xlsx import WorkbenchXLSXDocument


class Command(BaseCommand):
    help = "Analyze deal types"

    def add_arguments(self, parser):
        parser.add_argument("--from", type=dt.date.fromisoformat)
        parser.add_argument("--until", type=dt.date.fromisoformat)
        parser.add_argument(
            "--mailto",
            type=str,
        )

    def handle(self, **options):
        date_range = [
            options["from"] or dt.date.min,
            options["until"] or dt.date.max,
        ]

        pprint(options)

        value_types = ValueType.objects.in_bulk() | {None: None}
        # specialist_fields = SpecialistField.objects.select_related("value_type").in_bulk() | {None: None}

        pprint(value_types)
        # pprint(specialist_fields)

        accepted = (
            Deal.objects.filter(status=Deal.ACCEPTED, closed_on__range=date_range)
            .prefetch_related("values")
            .select_related("customer")
        )

        per_customer_and_value_type = defaultdict(lambda: defaultdict(lambda: Z2))
        for deal in accepted:
            for value in deal.values.all():
                per_customer_and_value_type[deal.customer][
                    value_types[value.type_id]
                ] += value.value

        projects = Project.objects.filter(created_at__date__range=date_range).filter(
            customer__in=per_customer_and_value_type.keys()
        )
        projected = dict(
            ProjectedInvoice.objects.filter(
                project__in=projects, project__closed_on__isnull=True
            )
            .order_by()
            .values("project")
            .annotate(gross_margin=Sum("gross_margin"))
            .values_list("project", "gross_margin")
        )

        invoiced = defaultdict(lambda: Z2)
        invoiced_per_project = (
            Invoice.objects.invoiced()
            .filter(project__in=projects)
            .order_by()
            .values("project")
            .annotate(Sum("total_excl_tax"), Sum("third_party_costs"))
        )
        for row in invoiced_per_project:
            invoiced[row["project"]] = (
                row["total_excl_tax__sum"] - row["third_party_costs__sum"]
            )

        # Subtract third party costs from logged costs which have not been
        # invoiced yet. Maybe we're double counting here but I'd rather have a
        # pessimistic outlook here.
        for row in (
            LoggedCost.objects.filter(
                service__project__in=projects,
                third_party_costs__isnull=False,
                invoice_service__isnull=True,
            )
            .order_by()
            .values("service__project")
            .annotate(Sum("third_party_costs"))
        ):
            invoiced[row["service__project"]] -= row["third_party_costs__sum"]
        gross_margin_projection = {
            id: max(projected.get(id, Z2), invoiced.get(id, Z2))
            for id in projected.keys() | invoiced.keys()
        }

        hours = (
            LoggedHours.objects.order_by()
            .filter(service__project__in=projects)
            .values("service__project", "rendered_by__specialist_field__value_type")
            .annotate(Sum("hours"))
        )
        project_hours = defaultdict(lambda: defaultdict(lambda: Z1))
        for row in hours:
            project_hours[row["service__project"]][
                value_types[row["rendered_by__specialist_field__value_type"]]
            ] += row["hours__sum"]

        customer_stats = {}

        for project in projects:
            c = customer_stats.setdefault(
                project.customer,
                {
                    "customer": project.customer,
                    "gross_margin_projection": Z2,
                    "accepted_by_value_type": per_customer_and_value_type[
                        project.customer
                    ],
                    "rendered_by_value_type": defaultdict(lambda: Z2),
                },
            )

            gmp = gross_margin_projection.get(project.id, Z2)

            c["gross_margin_projection"] += gmp

            hours = project_hours[project.id]
            if sum(hours.values()):
                for field, h in hours.items():
                    c["rendered_by_value_type"][field] += h / sum(hours.values()) * gmp

        # pprint(accepted)
        # pprint(gross_margin_projection)
        # pprint(project_hours)
        # pprint(projected)
        # pprint(invoiced)

        def discrepancy_value(c):
            accepted_sum = sum(c["accepted_by_value_type"].values())
            rendered_sum = sum(c["rendered_by_value_type"].values())

            if accepted_sum and rendered_sum:
                fractions = [
                    (
                        c["accepted_by_value_type"][f] / accepted_sum,
                        c["rendered_by_value_type"][f] / rendered_sum,
                    )
                    for f in value_types.values()
                    if c["accepted_by_value_type"][f] or c["rendered_by_value_type"][f]
                ]

                return sum(abs(frac[0] - frac[1]) ** 2 for frac in fractions)
            return 0

        customer_stats = [
            c | {"discrepancy_value": discrepancy_value(c)}
            for c in customer_stats.values()
        ]

        customer_stats = sorted(customer_stats, key=lambda c: c["discrepancy_value"])

        # pprint(per_customer_and_value_type)
        pprint(customer_stats)

        xlsx = WorkbenchXLSXDocument()
        xlsx.add_sheet("Anteile")
        value_type_list = list(value_types.values())

        first = [
            "Kunde",
            "Diskrepanz",
            "Bereinigter Umsatz (Prognose)",
        ]
        second = ["", "", ""]
        for value_type in value_type_list:
            first.extend((value_type.title if value_type else None, "", ""))
            second.extend(("Verkauft", "Gearbeitet", "Ratio"))

        table = []
        for c in customer_stats:
            row = [
                c["customer"],
                c["discrepancy_value"],
                c["gross_margin_projection"],
            ]
            for value_type in value_type_list:
                accepted = c["accepted_by_value_type"][value_type]
                rendered = c["rendered_by_value_type"][value_type]
                row.extend((
                    accepted,
                    rendered,
                    rendered / accepted if accepted else None,
                ))
            table.append(row)

        xlsx.table(None, [first, second, *table])
        filename = f"analyze-deals-{date_range[0]}-{date_range[1]}.xlsx"

        if options["mailto"]:
            mail = EmailMultiAlternatives(
                "Geschäfte und Werttypen",
                "",
                to=options["mailto"].split(","),
                reply_to=options["mailto"].split(","),
            )
            with io.BytesIO() as f:
                xlsx.workbook.save(f)
                f.seek(0)
                mail.attach(
                    filename,
                    f.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            mail.send()
        else:
            xlsx.workbook.save(filename)
