from django.contrib import admin

from . import models


@admin.register(models.Circle)
class CircleAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "circle", "is_removed"]
    list_filter = ["circle", "is_removed"]
