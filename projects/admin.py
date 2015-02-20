from django.contrib import admin

from projects.models import Project, Release


class ReleaseInline(admin.TabularInline):
    extra = 0
    model = Release


admin.site.register(
    Project,
    inlines=(ReleaseInline,),
    list_display=('title', 'status'),
    list_filter=('status',),
    raw_id_fields=('customer', 'contact', 'owned_by'),
)
admin.site.register(
    Release,
    raw_id_fields=('project',),
)
