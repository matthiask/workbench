from django.contrib import admin

from workbench.services.models import ServiceType


admin.site.register(
    ServiceType,
    list_display=("title", "billing_per_hour", "position"),
    list_editable=("position",),
)
