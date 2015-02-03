from django.contrib import admin

from deals.models import Funnel, Deal, RequiredService


class RequiredServiceInline(admin.TabularInline):
    extra = 0
    model = RequiredService


admin.site.register(Funnel)
admin.site.register(
    Deal,
    list_display=(
        'funnel', 'title', 'owned_by', 'estimated_value', 'status',
        'created_at'),
    list_display_links=('title',),
    list_filter=('funnel', 'status'),
    inlines=(RequiredServiceInline,),
)
