from django.utils.translation import gettext as _

from xlsxdocument import XLSXDocument

from workbench.contacts.models import PostalAddress


class WorkbenchXLSXDocument(XLSXDocument):
    def logged_hours(self, queryset):
        self.table_from_queryset(
            queryset.select_related(
                "created_by",
                "rendered_by",
                "service__project__owned_by",
                "invoice_service__invoice__owned_by",
                "invoice_service__invoice__project",
            ),
            additional=[
                ("service", lambda hours: hours.service),
                ("project", lambda hours: hours.service.project),
                (
                    "invoice",
                    lambda hours: hours.invoice_service.invoice
                    if hours.invoice_service
                    else None,
                ),
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
                ("service", lambda cost: cost.service),
                ("project", lambda cost: cost.service.project),
                (
                    "invoice",
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
                (field, getter(field))
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
                _("project"),
                _("responsible"),
                _("offered"),
                _("logbook"),
                _("undefined rate"),
                _("third party costs"),
                _("invoiced"),
                _("not archived"),
                _("total hours"),
                _("delta"),
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
