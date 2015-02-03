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
)
admin.site.register(Release)
