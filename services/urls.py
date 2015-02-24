from django.conf.urls import patterns, url

from services import views


urlpatterns = patterns(
    '',
    url(
        r'^rendered/$',
        views.RenderedServiceListView.as_view(),
        name='services_renderedservice_list'),
    url(
        r'^rendered/(?P<pk>\d+)/$',
        views.RenderedServiceDetailView.as_view(),
        name='services_renderedservice_detail'),
    url(
        r'^rendered/create/(?P<story>\d+)/$',
        views.RenderedServiceCreateView.as_view(),
        name='services_renderedservice_create'),
)
