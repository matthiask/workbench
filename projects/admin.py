from django.contrib import admin

from projects.models import Project, Release


class ReleaseInline(admin.TabularInline):
    extra = 0
    model = Release


class ProjectAdmin(admin.ModelAdmin):
    inlines = (ReleaseInline,)
    list_display = ('title', 'status')
    list_filter = ('status',)
    raw_id_fields = ('customer', 'contact', 'owned_by')


class ReleaseAdmin(admin.ModelAdmin):
    raw_id_fields = ('project',)


admin.site.register(Project, ProjectAdmin)
admin.site.register(Release, ReleaseAdmin)
