from django.contrib import admin

from offers import models


class OfferAdmin(admin.ModelAdmin):
    raw_id_fields = ('project', 'stories')


admin.site.register(models.Offer, OfferAdmin)
