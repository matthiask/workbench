from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django_fast_export.csv import StreamingCSVResponse, all_values, all_verbose_names


@admin.display(description=_("Export selected items as CSV"))
def export_selected_items(modeladmin, request, queryset):
    def generate():
        yield all_verbose_names(queryset.model)
        yield from (all_values(instance) for instance in queryset)

    filename = f"{queryset.model._meta.verbose_name_plural.lower()}.csv"
    return StreamingCSVResponse(generate(), filename=filename)
