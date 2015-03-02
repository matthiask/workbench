from django.conf.urls import url

from stories.models import Story, RenderedService
from stories.views import StoryDetailView, StoryMergeView
from tools.views import DetailView, DeleteView


urlpatterns = [
    url(
        r'^(?P<pk>\d+)/$',
        StoryDetailView.as_view(),
        name='stories_story_detail'),
    url(
        r'^(?P<pk>\d+)/delete/$',
        DeleteView.as_view(model=Story),
        name='stories_story_delete'),
    url(
        r'^(?P<pk>\d+)/merge/$',
        StoryMergeView.as_view(),
        name='stories_story_merge'),
    url(
        r'^rendered/(?P<pk>\d+)/$',
        DetailView.as_view(model=RenderedService),
        name='stories_renderedservice_detail'),
]
