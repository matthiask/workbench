from collections import defaultdict

from django.core.management import BaseCommand
from django.db.models import Sum
from django.utils.translation import activate, gettext as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedHours
from workbench.tools.formats import Z1
from workbench.tools.xlsx import WorkbenchXLSXDocument


def with_rate(row, field):
    row["rate"] = row[field] / row["hours"]
    return row


class Command(BaseCommand):
    def handle(self, **options):
        activate("de")

        invoiced_per_customer = {
            row["customer"]: row["total_excl_tax__sum"] - row["third_party_costs__sum"]
            for row in Invoice.objects.invoiced()
            .filter(project__isnull=False)
            .order_by()
            .values("customer")
            .annotate(Sum("total_excl_tax"), Sum("third_party_costs"))
        }
        hours = defaultdict(lambda: defaultdict(lambda: Z1))
        earned = defaultdict(lambda: defaultdict(lambda: Z1))
        customer_hours = defaultdict(lambda: Z1)
        user_hours = defaultdict(lambda: Z1)

        for row in (
            LoggedHours.objects.order_by()
            .values("service__project__customer", "rendered_by")
            .annotate(Sum("hours"))
        ):
            hours[row["service__project__customer"]][row["rendered_by"]] = row[
                "hours__sum"
            ]
            customer_hours[row["service__project__customer"]] += row["hours__sum"]
            user_hours[row["rendered_by"]] += row["hours__sum"]

        for customer, total_excl_tax in invoiced_per_customer.items():
            _c_hours = sum(hours[customer].values(), Z1)
            if not total_excl_tax:
                continue
            if not _c_hours:
                print(
                    "No hours for customer",
                    customer,
                    "with",
                    total_excl_tax,
                    Organization.objects.get(pk=customer),
                )
                continue
            for user, _u_hours in hours[customer].items():
                earned[customer][user] += _u_hours / _c_hours * total_excl_tax

        customers = sorted(
            (
                with_rate(
                    {
                        "customer": customer,
                        "invoiced": invoiced_per_customer.get(customer.id, Z1),
                        "hours": customer_hours[customer.id],
                    },
                    "invoiced",
                )
                for customer in Organization.objects.filter(id__in=earned.keys())
            ),
            key=lambda row: row["rate"],
            reverse=True,
        )
        users = sorted(
            (
                with_rate(
                    {
                        "user": user,
                        "earned": sum((c[user.id] for c in earned.values()), Z1),
                        "hours": user_hours[user.id],
                    },
                    "earned",
                )
                for user in User.objects.filter(id__in=user_hours)
            ),
            key=lambda row: row["rate"],
            reverse=True,
        )

        data = []
        data = [
            ["", "", "", _("user")] + [u["user"] for u in users],
            ["", "", "", _("earned")] + [u["earned"] for u in users],
            ["", "", "", _("hours")] + [u["hours"] for u in users],
            [_("customer"), _("invoiced"), _("hours"), _("rate")]
            + [u["rate"] for u in users],
        ]

        for c in customers:
            data.extend(
                [
                    [c["customer"], c["invoiced"], c["hours"], c["rate"]]
                    + [hours[c["customer"].id][u["user"].id] or None for u in users],
                    ["", "", "", ""]
                    + [earned[c["customer"].id][u["user"].id] or None for u in users],
                ]
            )

        xlsx = WorkbenchXLSXDocument()
        xlsx.add_sheet("profitability")
        xlsx.table(None, data)
        xlsx.workbook.save("profitability.xlsx")
