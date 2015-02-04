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

    url(
        r'^bootstrap/$',
        generic.TemplateView.as_view(template_name='bootstrap.html')),

    url(
        r'^deals/funnel/(?P<pk>\d+)/$',
        'deals.views.funnel_detail',
        name='funnel_detail'),

    url(r'^admin/', include(admin.site.urls)),
) + staticfiles_urlpatterns()
