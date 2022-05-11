from workbench.offers import models
from workbench.tools import admin


@admin.register(models.Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("project", "title", "offered_on", "owned_by", "status", "total")
    list_filter = ("status",)
    raw_id_fields = ("project",)
