from django.contrib import admin

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
    list_display = (
        'story', 'rendered_on', 'rendered_by', 'hours', 'description')
    raw_id_fields = ('story', 'created_by', 'rendered_by')


admin.site.register(Story, StoryAdmin)
admin.site.register(RenderedService, RenderedServiceAdmin)
