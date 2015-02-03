from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views import generic


urlpatterns = patterns(
    '',
    # Examples:
    # url(r'^$', 'ftool.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^$', generic.TemplateView.as_view(template_name='base.html')),

    url(r'^admin/', include(admin.site.urls)),
) + staticfiles_urlpatterns()
