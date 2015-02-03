from django.contrib import admin

from deals.models import Funnel, Deal, RequiredService


class RequiredServiceInline(admin.TabularInline):
    extra = 0
    model = RequiredService


admin.site.register(Funnel)
admin.site.register(
    Deal,
    inlines=(RequiredServiceInline,),
)
