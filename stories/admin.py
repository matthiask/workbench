from django.contrib import admin

from stories.models import Story


admin.site.register(
    Story,
    list_display=(
        'project', 'release', 'title', 'status'),
    list_display_links=('title',),
    list_filter=('status',),
)
