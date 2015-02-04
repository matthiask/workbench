from django.conf.urls import patterns, url

from deals import views


urlpatterns = patterns(
    '',
    url(
        r'^funnel/(?P<pk>\d+)/$',
        views.FunnelDetailView.as_view(),
        name='deals_funnel_detail'),

    url(
        r'^deal/$',
        views.DealListView.as_view(),
        name='deals_deal_list'),
    url(
        r'^deal/(?P<pk>\d+)/$',
        views.DealDetailView.as_view(),
        name='deals_deal_detail'),
)
