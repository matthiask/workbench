from django.conf.urls import url

from projects.forms import ProjectSearchForm, ProjectForm, TaskForm
from projects.models import Project, Task
from projects.views import (
    ProjectDetailView, CreateTaskView, OfferCreateView,
    TaskDetailView, TaskDeleteView)
from tools.views import (
    ListView, CreateView, UpdateView, DeleteView)


urlpatterns = [
    url(
        r'^$',
        ListView.as_view(
            model=Project,
            search_form_class=ProjectSearchForm,
            select_related=(
                'customer',
                'contact__organization',
                'owned_by',
            ),
        ),
        name='projects_project_list'),
    url(
        r'^(?P<pk>\d+)/$',
        ProjectDetailView.as_view(),
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
        r'^(?P<pk>\d+)/createtask/$',
        CreateTaskView.as_view(),
        name='projects_project_createtask'),
    url(
        r'^(?P<pk>\d+)/createoffer/$',
        OfferCreateView.as_view(),
        name='projects_project_createoffer'),

    # url(
    #     r'^(?P<pk>\d+)/estimation/$',
    #     EstimationView.as_view(),
    #     name='projects_project_estimation'),

    url(
        r'^tasks/(?P<pk>\d+)/$',
        TaskDetailView.as_view(),
        name='projects_task_detail'),
    url(
        r'^tasks/(?P<pk>\d+)/update/$',
        UpdateView.as_view(
            model=Task,
            form_class=TaskForm,
        ),
        name='projects_task_update'),
    url(
        r'^tasks/(?P<pk>\d+)/delete/$',
        TaskDeleteView.as_view(),
        name='projects_task_delete'),
    # url(
    #     r'^(?P<pk>\d+)/planning/$',
    #     views.PlanningView.as_view(),
    #     name='projects_project_planning'),
]
