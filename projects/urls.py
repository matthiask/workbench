from django.conf.urls import url
from django.shortcuts import redirect

from projects.forms import (
    ProjectSearchForm, ProjectForm, TaskForm, CommentForm)
from projects.models import Project, Task, Comment
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
        lambda request, pk: redirect('overview/'),
        name='projects_project_detail'),
    url(
        r'^(?P<pk>\d+)/overview/$',
        ProjectDetailView.as_view(project_view='overview'),
        name='projects_project_overview'),
    url(
        r'^(?P<pk>\d+)/tasks/$',
        ProjectDetailView.as_view(project_view='tasks'),
        name='projects_project_tasks'),
    url(
        r'^(?P<pk>\d+)/services/$',
        ProjectDetailView.as_view(project_view='services'),
        name='projects_project_services'),

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

    url(
        r'^comments/(?P<pk>\d+)/update/$',
        UpdateView.as_view(
            model=Comment,
            form_class=CommentForm,
            template_name='modalform.html',
        ),
        name='projects_comment_update'),
    url(
        r'^comments/(?P<pk>\d+)/delete/$',
        DeleteView.as_view(
            model=Comment,
        ),
        name='projects_comment_delete'),
]
