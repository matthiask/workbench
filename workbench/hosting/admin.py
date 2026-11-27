from workbench.hosting import models
from workbench.tools import admin


@admin.register(models.Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ["title", "is_archived"]
    search_fields = ["title", "notes"]


class SiteContactInline(admin.TabularInline):
    model = models.SiteContact
    raw_id_fields = ["person"]
    extra = 0


@admin.register(models.Site)
class SiteAdmin(admin.ModelAdmin):
    inlines = [SiteContactInline]
    list_display = ["title", "server", "customer", "is_archived"]
    list_filter = ["server", "is_archived"]
    list_select_related = ["server", "customer"]
    raw_id_fields = ["customer"]
    search_fields = ["title", "domains", "customer__name"]
