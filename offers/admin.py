from django.contrib import admin

from offers import models


class OfferAdmin(admin.ModelAdmin):
    list_display = (
        'project', 'title', 'offered_on', 'owned_by', 'status', 'total')
    list_filter = ('status',)
    raw_id_fields = ('project', 'stories')


admin.site.register(models.Offer, OfferAdmin)
