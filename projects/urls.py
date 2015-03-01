from django.conf.urls import url

from projects import views


urlpatterns = [
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

    url(
        r'^(?P<project_id>\d+)/release/(?P<pk>\d+)/$',
        views.ReleaseDetailView.as_view(),
        name='projects_release_detail'),
    url(
        r'^(?P<pk>\d+)/createstory/$',
        views.StoryCreateView.as_view(),
        name='projects_project_createstory'),
    url(
        r'^(?P<pk>\d+)/estimation/$',
        views.EstimationView.as_view(),
        name='projects_project_estimation'),
    # url(
    #     r'^(?P<pk>\d+)/planning/$',
    #     views.PlanningView.as_view(),
    #     name='projects_project_planning'),
]
