from django.contrib import admin

from projects.models import Project, Task, Attachment, Comment


class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'customer', 'owned_by', 'status')
    list_filter = ('status',)
    raw_id_fields = ('customer', 'contact', 'owned_by')


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'project', 'title', 'status', 'type', 'priority', 'owned_by')
    raw_id_fields = ('project', 'service')


admin.site.register(Project, ProjectAdmin)
admin.site.register(Task, TaskAdmin)
