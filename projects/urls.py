from django.conf.urls import url

from projects.forms import ProjectForm
from projects.models import Project
from projects.views import ProjectListView, StoryCreateView, EstimationView
from tools.views import (
    DetailView, CreateView, UpdateView, DeleteView)


urlpatterns = [
    url(
        r'^$',
        ProjectListView.as_view(),
        name='projects_project_list'),
    url(
        r'^(?P<pk>\d+)/$',
        DetailView.as_view(model=Project),
        name='projects_project_detail'),
    url(
        r'^create/$',
        CreateView.as_view(
            form_class=ProjectForm,
            model=Project,
        ),
        name='projects_project_create'),
    url(
        r'^(?P<pk>\d+)/update/$',
        UpdateView.as_view(
            form_class=ProjectForm,
            model=Project,
        ),
        name='projects_project_update'),
    url(
        r'^(?P<pk>\d+)/delete/$',
        DeleteView.as_view(model=Project),
        name='projects_project_delete'),

    url(
        r'^(?P<pk>\d+)/createstory/$',
        StoryCreateView.as_view(),
        name='projects_project_createstory'),
    url(
        r'^(?P<pk>\d+)/estimation/$',
        EstimationView.as_view(),
        name='projects_project_estimation'),
    # url(
    #     r'^(?P<pk>\d+)/planning/$',
    #     views.PlanningView.as_view(),
    #     name='projects_project_planning'),
]
