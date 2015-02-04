from django.conf.urls import patterns, url

from projects import views


urlpatterns = patterns(
    '',
    url(
        r'^project/(?P<pk>\d+)/$',
        views.ProjectDetailView.as_view(),
        name='projects_project_detail'),
)
