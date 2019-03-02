from xlsxdocument import XLSXDocument


class WorkbenchXLSXDocument(XLSXDocument):
    def logged_hours(self, queryset):
        self.table_from_queryset(
            queryset.select_related(
                "rendered_by", "service__project__owned_by", "invoice"
            ),
            additional=[
                ("service", lambda hours: hours.service),
                ("project", lambda hours: hours.service.project),
                ("invoice", lambda hours: hours.invoice),
            ],
        )

    def logged_costs(self, queryset):
        self.table_from_queryset(queryset)

    def invoices(self, queryset):
        self.table_from_queryset(queryset)
