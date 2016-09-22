from django.contrib import admin

from offers import models


class ServiceInline(admin.TabularInline):
    model = models.Service
    extra = 0


class OfferAdmin(admin.ModelAdmin):
    list_display = (
        'project', 'title', 'offered_on', 'owned_by', 'status', 'total')
    list_filter = ('status',)
    inlines = [ServiceInline]
    raw_id_fields = ('project',)


class EffortInline(admin.TabularInline):
    model = models.Effort
    extra = 0


class CostInline(admin.TabularInline):
    model = models.Cost
    extra = 0


class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        'offer', 'title', 'description', 'position',
        'effort_hours', 'cost', 'approved_hours')
    inlines = [EffortInline, CostInline]


admin.site.register(models.Offer, OfferAdmin)
admin.site.register(models.Service, ServiceAdmin)
