from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from stories.models import Story, RequiredService, RenderedService


class RequiredServiceInline(admin.TabularInline):
    model = RequiredService
    extra = 0


class StoryAdmin(admin.ModelAdmin):
    list_display = (
        'project', 'release', 'title', 'status')
    list_display_links = ('title',)
    list_filter = ('status',)
    inlines = (RequiredServiceInline,)
    raw_id_fields = ('requested_by', 'owned_by', 'project', 'release')


class RenderedServiceAdmin(admin.ModelAdmin):
    date_hierarchy = 'rendered_on'
    list_display = (
        'project', 'story', 'rendered_on', 'rendered_by', 'hours',
        'description')
    list_display_links = ('project', 'story')
    list_select_related = (
        'story__project', 'rendered_by')
    raw_id_fields = ('story', 'created_by', 'rendered_by')

    def project(self, instance):
        return instance.story.project

    project.short_description = _('project')


admin.site.register(Story, StoryAdmin)
admin.site.register(RenderedService, RenderedServiceAdmin)
