from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _

from projects.forms import (
    ProjectSearchForm, ProjectForm, StoryForm, EstimationForm)
from projects.models import Project, Release
from stories.models import Story
from tools.views import ListView, DetailView, CreateView, UpdateView


class ProjectViewMixin(object):
    model = Project


class ProjectListView(ProjectViewMixin, ListView):
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'customer',
            'contact__organization',
        )

        self.search_form = ProjectSearchForm(self.request.GET)
        if self.search_form.is_valid():
            data = self.search_form.cleaned_data
            if data.get('s'):
                queryset = queryset.filter(status=data.get('s'))

        return queryset


class ProjectDetailView(ProjectViewMixin, DetailView):
    pass


class ProjectCreateView(ProjectViewMixin, CreateView):
    form_class = ProjectForm

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'owned_by': self.request.user.pk,
        })
        form_class = self.get_form_class()
        return form_class(data, files, **kwargs)


class ProjectUpdateView(ProjectViewMixin, UpdateView):
    form_class = ProjectForm


class ReleaseViewMixin(object):
    model = Release


class ReleaseDetailView(ReleaseViewMixin, DetailView):
    def get_object(self):
        try:
            return get_object_or_404(
                self.get_queryset(),
                project_id=self.kwargs['project_id'],
                pk=self.kwargs['pk'])
        except KeyError:
            raise ImproperlyConfigured(
                "Values 'project_id' and 'pk' not available.")


class StoryCreateView(CreateView):
    model = Story

    def allow_create(self):
        self.project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return True

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'requested_by': self.request.user.id,
            'owned_by': self.request.user.id,
            'release': self.project.releases.filter(is_default=True).first(),
        })
        return StoryForm(data, files, project=self.project, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.allow_create():
            return redirect('../')

        form = self.get_form(request.POST, request.FILES)
        if form.is_valid():
            story = form.save(commit=False)
            story.requested_by = self.request.user
            story.project = self.project
            story.save()

            messages.success(
                self.request,
                _('%(class)s "%(object)s" has been successfully created.') % {
                    'class': story._meta.verbose_name,
                    'object': story,
                })

            if '_continue' in request.POST:
                return redirect('.')
            else:
                return HttpResponse('Thanks', status=201)  # Created

        return self.render_to_response(self.get_context_data(form=form))


class EstimationView(ProjectViewMixin, UpdateView):
    template_name_suffix = '_estimation'
    form_class = EstimationForm
