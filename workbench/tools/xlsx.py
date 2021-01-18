from collections import defaultdict
from itertools import chain

from django.utils.text import capfirst, slugify
from django.utils.translation import gettext as _

from xlsxdocument import XLSXDocument

from workbench.contacts.models import PostalAddress
from workbench.templatetags.workbench import label
from workbench.tools.formats import Z1


class WorkbenchXLSXDocument(XLSXDocument):
    def logged_hours(self, queryset):
        queryset = queryset.select_related(
            "created_by",
            "rendered_by",
            "service__project__owned_by",
            "invoice_service__invoice__owned_by",
            "invoice_service__invoice__project",
        )

        self.table_from_queryset(
            queryset,
            additional=[
                (capfirst(_("hourly rate")), lambda hours: hours.service.effort_rate),
                (capfirst(_("project")), lambda hours: hours.service.project),
                (
                    capfirst(_("invoice")),
                    lambda hours: hours.invoice_service.invoice
                    if hours.invoice_service
                    else None,
                ),
            ],
        )

        by_service_and_user = defaultdict(lambda: defaultdict(lambda: Z1))
        by_user = defaultdict(lambda: Z1)
        by_service_and_month = defaultdict(lambda: defaultdict(lambda: Z1))
        by_user_and_month = defaultdict(lambda: defaultdict(lambda: Z1))
        by_month = defaultdict(lambda: Z1)

        for h in queryset:
            by_service_and_user[h.service][h.rendered_by] += h.hours
            by_user[h.rendered_by] += h.hours

            month = h.rendered_on.replace(day=1)
            by_service_and_month[h.service][month] += h.hours
            by_user_and_month[h.rendered_by][month] += h.hours
            by_month[month] += h.hours

        self.add_sheet(slugify(_("By service and user")))
        users = sorted(
            set(
                chain.from_iterable(
                    users.keys() for users in by_service_and_user.values()
                )
            )
        )

        self.table(
            [
                capfirst(t)
                for t in [
                    _("project"),
                    _("service"),
                    _("hourly rate"),
                    _("total"),
                    _("total"),
                ]
            ]
            + [user.get_short_name() for user in users],
            [
                [capfirst(_("total")), "", "", sum(by_user.values(), Z1), ""]
                + [by_user.get(user) for user in users]
            ]
            + [
                [
                    service.project,
                    service,
                    service.effort_rate,
                    sum(by_users.values(), Z1),
                    None
                    if service.effort_rate is None
                    else sum(by_users.values(), Z1) * service.effort_rate,
                ]
                + [by_users.get(user) for user in users]
                for service, by_users in sorted(
                    by_service_and_user.items(),
                    key=lambda row: (row[0].project_id, row[0].position),
                )
            ],
        )

        self.add_sheet(slugify(_("By service and month")))
        months = sorted(
            set(
                chain.from_iterable(
                    months.keys() for months in by_service_and_month.values()
                )
            )
        )
        self.table(
            [
                capfirst(t)
                for t in [
                    _("project"),
                    _("service"),
                    _("hourly rate"),
                    _("total"),
                    _("total"),
                ]
            ]
            + months,
            [
                [capfirst(_("total")), "", "", sum(by_month.values(), Z1), ""]
                + [by_month.get(month) for month in months]
            ]
            + [
                [
                    service.project,
                    service,
                    service.effort_rate,
                    sum(by_months.values(), Z1),
                    None
                    if service.effort_rate is None
                    else sum(by_months.values(), Z1) * service.effort_rate,
                ]
                + [by_months.get(month) for month in months]
                for service, by_months in sorted(
                    by_service_and_month.items(),
                    key=lambda row: (row[0].project_id, row[0].position),
                )
            ],
        )

        self.add_sheet(slugify(_("By user and month")))
        months = sorted(
            set(
                chain.from_iterable(
                    months.keys() for months in by_user_and_month.values()
                )
            )
        )
        self.table(
            [
                capfirst(t)
                for t in [
                    _("user"),
                    _("total"),
                ]
            ]
            + months,
            [
                [capfirst(_("total")), sum(by_month.values(), Z1)]
                + [by_month.get(month) for month in months]
            ]
            + [
                [
                    user,
                    sum(by_months.values(), Z1),
                ]
                + [by_months.get(month) for month in months]
                for user, by_months in sorted(
                    by_user_and_month.items(),
                    # key=lambda row: (row[0].project_id, row[0].position),
                )
            ],
        )

    def logged_costs(self, queryset):
        self.table_from_queryset(
            queryset.select_related(
                "created_by",
                "rendered_by",
                "service__project__owned_by",
                "invoice_service__invoice__owned_by",
                "invoice_service__invoice__project",
            ),
            additional=[
                (capfirst(_("service")), lambda cost: cost.service),
                (capfirst(_("project")), lambda cost: cost.service.project),
                (
                    capfirst(_("invoice")),
                    lambda cost: cost.invoice_service.invoice
                    if cost.invoice_service
                    else None,
                ),
            ],
        )

    def people(self, queryset):
        addresses = {
            address.person_id: address
            for address in PostalAddress.objects.filter(person__in=queryset).reverse()
        }

        def getter(field):
            def attribute(person):
                return getattr(addresses.get(person.id), field, "")

            return attribute

        self.table_from_queryset(
            queryset.select_related("organization", "primary_contact"),
            additional=[
                (str(label(PostalAddress, field)), getter(field))
                for field in [
                    "street",
                    "house_number",
                    "address_suffix",
                    "postal_code",
                    "city",
                    "country",
                    "postal_address_override",
                ]
            ],
        )

    def project_budget_statistics(self, statistics):
        self.add_sheet(_("projects"))
        self.table(
            [
                capfirst(_("project")),
                capfirst(_("responsible")),
                _("Offered"),
                _("Logbook"),
                _("Undefined rate"),
                capfirst(_("third party costs")),
                _("Invoiced"),
                _("Not archived"),
                _("Total hours"),
                _("Delta"),
            ],
            [
                (
                    project["project"],
                    project["project"].owned_by.get_short_name(),
                    project["offered"],
                    project["logbook"],
                    project["effort_hours_with_rate_undefined"],
                    project["third_party_costs"],
                    project["invoiced"],
                    project["not_archived"],
                    project["hours"],
                    project["delta"],
                )
                for project in statistics["statistics"]
            ],
        )
