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
    url(
        r'^create/$',
        views.ProjectCreateView.as_view(),
        name='projects_project_create'),
    url(
        r'^(?P<pk>\d+)/update/$',
        views.ProjectUpdateView.as_view(),
        name='projects_project_update'),
)
