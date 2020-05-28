from workbench.tools import admin

from . import models


@admin.register(models.Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("project", "title", "offered_on", "owned_by", "status", "total")
    list_filter = ("status",)
    raw_id_fields = ("project",)
