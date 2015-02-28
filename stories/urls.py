from django.conf.urls import url

from stories import views


urlpatterns = [
    url(
        r'^(?P<pk>\d+)/$',
        views.StoryDetailView.as_view(),
        name='stories_story_detail'),
]
