from xlsxdocument import XLSXDocument

from workbench.contacts.models import PostalAddress


class WorkbenchXLSXDocument(XLSXDocument):
    def logged_hours(self, queryset):
        self.table_from_queryset(
            queryset.select_related(
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
        self.table_from_queryset(queryset)

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
