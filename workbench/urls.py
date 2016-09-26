from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.shortcuts import render

from workbench import views


urlpatterns = [
    url(r'^$', render, {'template_name': 'start.html'}),
    url(r'^bootstrap/$', render, {'template_name': 'bootstrap.html'}),
    url(r'^404/$', render, {'template_name': '404.html'}),

    url(r'^admin/', admin.site.urls),

    url(r'^accounts/', include('accounts.urls')),
    url(r'^activities/', include('activities.urls')),
    url(r'^contacts/', include('contacts.urls')),
    url(r'^deals/', include('deals.urls')),
    url(r'^logbook/', include('logbook.urls')),
    url(r'^offers/', include('offers.urls')),
    url(r'^projects/', include('projects.urls')),
    url(r'^invoices/', include('invoices.urls')),

    url(r'^search/$', views.search, name='search'),
    url(r'^history/(\w+\.\w+)/(\d+)/$', views.history, name='history'),
]

if settings.DEBUG:
    import debug_toolbar
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns = urlpatterns + [
        url(r'^__debug__/', debug_toolbar.urls),
    ] + staticfiles_urlpatterns()
