from django.contrib import admin

import reversion

from activities.models import Activity


class ActivityAdmin(reversion.VersionAdmin):
    list_display = (
        'contact', 'deal', 'title', 'owned_by', 'due_on', 'completed_at')
    list_display_links = ('title',)
    raw_id_fields = ('contact', 'deal', 'owned_by')


admin.site.register(Activity, ActivityAdmin)
