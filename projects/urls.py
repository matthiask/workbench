from django.conf.urls import url
from django.shortcuts import redirect

from invoices.forms import CreateInvoiceForm
from invoices.models import Invoice
from logbook.forms import LoggedHoursForm, LoggedCostForm
from logbook.models import LoggedHours, LoggedCost
from offers.forms import CreateOfferForm
from offers.models import Offer
from projects.forms import (
    ProjectSearchForm, ProjectForm, ApprovedHoursForm, TaskSearchForm,
    TaskForm, CommentForm)
from projects.models import Project, Task, Comment
from projects.views import (
    ProjectDetailView, CreateRelatedView, TaskDetailView, TaskDeleteView)
from tools.views import (
    ListView, CreateView, UpdateView, DeleteView)


urlpatterns = [
    url(
        r'^$',
        ListView.as_view(
            model=Project,
            search_form_class=ProjectSearchForm,
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
        r'^(?P<pk>\d+)/costs/$',
        ProjectDetailView.as_view(project_view='costs'),
        name='projects_project_costs'),

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
        r'^(?P<pk>\d+)/approved-hours/$',
        UpdateView.as_view(
            form_class=ApprovedHoursForm,
            model=Project,
        ),
        name='projects_project_approved_hours'),
    url(
        r'^(?P<pk>\d+)/delete/$',
        DeleteView.as_view(model=Project),
        name='projects_project_delete'),

    url(
        r'^(?P<pk>\d+)/createtask/$',
        CreateRelatedView.as_view(
            model=Task,
            form_class=TaskForm,
        ),
        name='projects_project_createtask'),
    url(
        r'^(?P<pk>\d+)/createoffer/$',
        CreateRelatedView.as_view(
            model=Offer,
            form_class=CreateOfferForm,
        ),
        name='projects_project_createoffer'),
    url(
        r'^(?P<pk>\d+)/createinvoice/$',
        CreateRelatedView.as_view(
            model=Invoice,
            form_class=CreateInvoiceForm,
        ),
        name='projects_project_createinvoice'),

    # url(
    #     r'^(?P<pk>\d+)/estimation/$',
    #     EstimationView.as_view(),
    #     name='projects_project_estimation'),

    url(
        r'^tasks/$',
        ListView.as_view(
            model=Task,
            search_form_class=TaskSearchForm,
            show_create_button=False,
        ),
        name='projects_task_list'),
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

    # HOURS
    url(
        r'^(?P<pk>\d+)/createcost/$',
        CreateRelatedView.as_view(
            model=LoggedHours,
            form_class=LoggedHoursForm,
        ),
        name='projects_project_createhours'),

    # COSTS
    url(
        r'^(?P<pk>\d+)/createcost/$',
        CreateRelatedView.as_view(
            model=LoggedCost,
            form_class=LoggedCostForm,
        ),
        name='projects_project_createcost'),
    url(
        r'^cost/(?P<pk>\d+)/update/$',
        UpdateView.as_view(
            model=LoggedCost,
            form_class=LoggedCostForm,
        ),
        name='logbook_loggedcost_update'),
    url(
        r'^cost/(?P<pk>\d+)/delete/$',
        DeleteView.as_view(
            model=LoggedCost,
            template_name='modal_confirm_delete.html',
        ),
        name='logbook_loggedcost_delete'),
]
