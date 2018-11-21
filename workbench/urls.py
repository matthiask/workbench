from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.shortcuts import render

from workbench import views


urlpatterns = [
    url(r"^$", render, {"template_name": "start.html"}),
    url(r"^bootstrap/$", render, {"template_name": "bootstrap.html"}),
    url(r"^404/$", render, {"template_name": "404.html"}),
    url(r"^admin/", admin.site.urls),
    url(r"^accounts/", include("workbench.accounts.urls")),
    url(r"^calendar/", include("workbench.calendar.urls")),
    url(r"^search/$", views.search, name="search"),
    url(r"^history/(\w+\.\w+)/([0-9]+)/$", views.history, name="history"),
]

if settings.DEBUG:
    import debug_toolbar
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns = (
        urlpatterns
        + [url(r"^__debug__/", include(debug_toolbar.urls))]
        + staticfiles_urlpatterns()
    )
