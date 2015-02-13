from django.conf.urls import patterns, url

from projects import views


urlpatterns = patterns(
    '',
    url(
        r'^$',
        views.ProjectListView.as_view(),
        name='projects_project_list'),
    url(
        r'^(?P<pk>\d+)/$',
        views.ProjectDetailView.as_view(),
        name='projects_project_detail'),
)
