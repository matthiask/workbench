from django.contrib import admin

from audit.models import LoggedAction


admin.site.register(LoggedAction)
