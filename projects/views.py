from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404

from projects.forms import (
    ProjectSearchForm, ProjectForm, StoryFormset, EstimationForm)
from projects.models import Project, Release
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


class StoryInventoryView(ProjectViewMixin, UpdateView):
    template_name_suffix = '_storyinventory'

    def get_form(self, data=None, files=None, **kwargs):
        return StoryFormset(data, files, **kwargs)


class EstimationView(ProjectViewMixin, UpdateView):
    template_name_suffix = '_estimation'
    form_class = EstimationForm
