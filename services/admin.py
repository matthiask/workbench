from django.contrib import admin

from services.models import ServiceType, RenderedService


admin.site.register(
    ServiceType,
    list_display=('title', 'billing_per_hour', 'position'),
    list_editable=('position',),
)
admin.site.register(
    RenderedService,
    list_display=(
        'story', 'rendered_on', 'rendered_by', 'hours', 'description'),
    raw_id_fields=('story', 'created_by', 'rendered_by'),
)
