from django.conf.urls import patterns, url

from deals import views


urlpatterns = patterns(
    '',
    url(
        r'^funnel/(?P<pk>\d+)/$',
        views.FunnelDetailView.as_view(),
        name='funnel_detail'),
)
