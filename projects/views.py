from collections import namedtuple
from decimal import Decimal
import itertools

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext_lazy as _

from logbook.forms import LoggedHoursForm
from logbook.models import LoggedHours
from offers.forms import CreateOfferForm
from offers.models import Offer, Service
from projects.forms import CommentForm, TaskForm
from projects.models import Project, Task, Comment
from tools.history import changes
from tools.views import DetailView, CreateView, DeleteView


class CreateTaskView(CreateView):
    model = Task

    def get_form(self, data=None, files=None, **kwargs):
        self.project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return TaskForm(
            data,
            files,
            project=self.project,
            request=self.request,
            **kwargs)


class OfferCreateView(CreateView):
    model = Offer

    def get_form(self, data=None, files=None, **kwargs):
        self.project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return CreateOfferForm(
            data,
            files,
            project=self.project,
            request=self.request,
            **kwargs)


ServiceTasks = namedtuple('ServiceTasks', 'service approved logged tasks')


class ServicesView(object):
    def __init__(self, project):
        self.project = project

        self.tasks = self.project.tasks.order_by(
            'service__offer__offered_on',
            'service',
            '-priority',
            'pk',
        ).select_related('owned_by', 'service__offer').annotate(
            logged_hours=Sum('loggedhours__hours'),
        )

        self.services = {}
        for key, group in itertools.groupby(
                self.tasks,
                lambda task: task.service_id
        ):
            group = list(group)
            self.services[key] = ServiceTasks(
                group[0].service,
                group[0].service.approved_hours if group[0].service else 0,
                sum(((task.logged_hours or 0) for task in group), Decimal()),
                group,
            )

    def __iter__(self):
        if None in self.services:
            yield self.services[None]

        for service in Service.objects.filter(offer__project=self.project):
            if service.id in self.services:
                yield self.services[service.id]
            else:
                yield ServiceTasks(
                    service,
                    service.approved_hours,
                    0,
                    [],
                )


ServiceCosts = namedtuple('ServiceCosts', 'service offered logged costs')


class CostView(object):
    def __init__(self, project):
        self.project = project

        self.costs = self.project.loggedcosts.order_by(
            'service',
            'rendered_on',
        ).select_related('created_by')

        self.services = {}
        for key, group in itertools.groupby(
                self.costs,
                lambda cost: cost.service_id,
        ):
            group = list(group)
            self.services[key] = list(group)

    def __iter__(self):
        if None in self.services:
            yield ServiceCosts(
                None,
                0,
                sum((c.cost for c in self.services[None]), 0),
                self.services[None])

        for service in Service.objects.filter(
            offer__project=self.project,
        ).prefetch_related('costs'):
            if service.id in self.services or service.costs.all():
                entries = self.services.get(service.id, [])
                yield ServiceCosts(
                    service,
                    sum((c.cost for c in service.costs.all()), 0),
                    sum((c.cost for c in entries), 0),
                    entries)


class ProjectDetailView(DetailView):
    model = Project
    project_view = None

    def get_context_data(self, **kwargs):
        if self.project_view == 'tasks':
            kwargs['tasks'] = ServicesView(self.object)

        elif self.project_view == 'costs':
            kwargs['costs'] = CostView(self.object)

        return super().get_context_data(**kwargs)


class TaskDetailView(DetailView):
    model = Task

    FORMS = {
        'comment_form': (
            Comment, CommentForm, {'prefix': 'comment'}),
        # 'attachment_form': (
        #     AttachmentForm, Attachment, {'prefix': 'attachment'}),
        'logbook_form': (
            LoggedHours, LoggedHoursForm, {'prefix': 'logbook'}),
    }

    def get_context_data(self, **kwargs):
        ch = [
            (change.version.created_at, 'change', change)
            for change in changes(self.object, (
                'title', 'description', 'type', 'priority', 'owned_by',
                'service', 'status', 'closed_at', 'due_on',
            ))[1:]
        ]

        ch.extend(
            (comment.created_at, 'comment', comment)
            for comment in self.object.comments.select_related('created_by')
        )

        for key, cfg in self.FORMS.items():
            if key not in kwargs:
                kwargs[key] = cfg[1](
                    task=self.object,
                    request=self.request,
                    **cfg[2])

        # kwargs['recent_rendered'] =\
            # self.object.renderedservices.select_related('rendered_by')[:5]
        return super().get_context_data(changes=sorted(ch), **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = {}

        for key, cfg in self.FORMS.items():
            if request.POST.get('form') == key:
                if not cfg[0].allow_create(request):
                    return redirect(self.object)

                context[key] = form = cfg[1](
                    request.POST,
                    request.FILES,
                    task=self.object,
                    request=self.request,
                    **cfg[2])

                if form.is_valid():
                    instance = form.save()
                    messages.success(self.request, _(
                        "%(class)s '%(object)s' has been successfully created."
                    ) % {
                        'class': instance._meta.verbose_name,
                        'object': instance,
                    })

                return redirect(self.object)

        return self.render_to_response(self.get_context_data(**context))


class TaskDeleteView(DeleteView):
    model = Task

    def get_success_url(self):
        return self.object.project.urls.url('tasks')
