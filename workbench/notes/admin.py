from django.contrib import admin

from . import models


@admin.register(models.Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["title", "content_object", "created_by", "created_at"]
    search_fields = ["title", "description"]
