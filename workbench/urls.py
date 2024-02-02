from django.conf import settings
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path, re_path

from workbench import views


urlpatterns = [
    path("", render, {"template_name": "start.html"}),
    path("bootstrap/", render, {"template_name": "bootstrap.html"}),
    path("404/", render, {"template_name": "404.html"}),
    re_path(r"^admin/", admin.site.urls),
    path("accounts/", include("workbench.accounts.urls")),
    path("calendar/", include("workbench.calendar.urls")),
    path("search/", views.search, name="search"),
    re_path(r"^history/(\w+\.\w+)/([0-9]+)/$", views.history, name="history"),
]

if settings.DEBUG:
    import debug_toolbar
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns = (
        urlpatterns
        + [path("__debug__/", include(debug_toolbar.urls))]
        + staticfiles_urlpatterns()
    )
