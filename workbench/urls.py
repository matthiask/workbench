from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

import vanilla

from workbench import views


urlpatterns = [
    url(r'^$', vanilla.TemplateView.as_view(template_name='start.html')),
    url(
        r'^bootstrap/$',
        vanilla.TemplateView.as_view(template_name='bootstrap.html')),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^accounts/', include('accounts.urls')),
    url(r'^activities/', include('activities.urls')),
    url(r'^contacts/', include('contacts.urls')),
    url(r'^deals/', include('deals.urls')),
    url(r'^offers/', include('offers.urls')),
    url(r'^projects/', include('projects.urls')),
    url(r'^stories/', include('stories.urls')),
    url(r'^invoices/', include('invoices.urls')),

    url(r'^search/$', views.search, name='search'),

] + staticfiles_urlpatterns()
