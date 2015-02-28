from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

import vanilla

from ftool import views


urlpatterns = [
    url(r'^$', vanilla.TemplateView.as_view(template_name='base.html')),
    url(
        r'^bootstrap/$',
        vanilla.TemplateView.as_view(template_name='bootstrap.html')),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^accounts/', include('accounts.urls')),
    url(r'^contacts/', include('contacts.urls')),
    url(r'^deals/', include('deals.urls')),
    url(r'^projects/', include('projects.urls')),
    url(r'^services/', include('services.urls')),

    url(r'^search/$', views.search, name='search'),

] + staticfiles_urlpatterns()
