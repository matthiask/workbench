from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

import vanilla


urlpatterns = patterns(
    '',
    url(r'^$', vanilla.TemplateView.as_view(template_name='base.html')),
    url(
        r'^bootstrap/$',
        vanilla.TemplateView.as_view(template_name='bootstrap.html')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/', include('django.contrib.auth.urls')),

    url(r'^contacts/', include('contacts.urls')),
    url(r'^deals/', include('deals.urls')),
    url(r'^projects/', include('projects.urls')),

) + staticfiles_urlpatterns()
