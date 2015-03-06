from django.contrib import admin

import reversion

from projects.models import Project, Release


class ReleaseInline(admin.TabularInline):
    extra = 0
    model = Release


class ProjectAdmin(reversion.VersionAdmin):
    inlines = (ReleaseInline,)
    list_display = ('title', 'status')
    list_filter = ('status',)
    raw_id_fields = ('customer', 'contact', 'owned_by')


class ReleaseAdmin(reversion.VersionAdmin):
    raw_id_fields = ('project',)


admin.site.register(Project, ProjectAdmin)
admin.site.register(Release, ReleaseAdmin)
