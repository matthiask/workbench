from django.conf.urls import url

from stories import views


urlpatterns = [
    url(
        r'^(?P<pk>\d+)/$',
        views.StoryDetailView.as_view(),
        name='stories_story_detail'),
    url(
        r'^(?P<pk>\d+)/delete/$',
        views.StoryDeleteView.as_view(),
        name='stories_story_delete'),

    url(
        r'^rendered/$',
        views.RenderedServiceListView.as_view(),
        name='stories_renderedservice_list'),
    url(
        r'^rendered/(?P<pk>\d+)/$',
        views.RenderedServiceDetailView.as_view(),
        name='stories_renderedservice_detail'),
    url(
        r'^rendered/create/(?P<story>\d+)/$',
        views.RenderedServiceCreateView.as_view(),
        name='stories_renderedservice_create'),
]
