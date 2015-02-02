from django.contrib import admin

from projects.models import Project, Release


admin.site.register(Project)
admin.site.register(Release)
