from django.contrib import admin

from projects.models import Project


class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'customer', 'owned_by', 'status')
    list_filter = ('status',)
    raw_id_fields = ('customer', 'contact', 'owned_by')


admin.site.register(Project, ProjectAdmin)
