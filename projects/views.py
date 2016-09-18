from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext_lazy as _

from logbook.forms import LoggedHoursForm
from logbook.models import LoggedHours
from offers.forms import CreateOfferForm
from offers.models import Offer
from projects.forms import CommentForm, TaskForm
from projects.models import Project, Task, Comment
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


# class EstimationView(UpdateView):
#     model = Project
#
#     template_name_suffix = '_estimation'
#     form_class = EstimationForm


class ProjectDetailView(DetailView):
    model = Project

    def get_context_data(self, **kwargs):
        view = self.request.GET.get('view')
        if view == 'services':
            kwargs['tasks'] = self.object.tasks.order_by(
                'service__offer',
                'service',
                '-priority',
                'pk',
            ).select_related('owned_by', 'service__offer')
            kwargs['tasks_view'] = 'services'

        else:
            kwargs['tasks'] = self.object.tasks.select_related('owned_by')
            kwargs['tasks_view'] = 'tasks'

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
        for key, cfg in self.FORMS.items():
            if key not in kwargs:
                kwargs[key] = cfg[1](
                    task=self.object,
                    request=self.request,
                    **cfg[2])

        # kwargs['recent_rendered'] =\
            # self.object.renderedservices.select_related('rendered_by')[:5]
        return super().get_context_data(**kwargs)

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
        return self.object.project.get_absolute_url()
