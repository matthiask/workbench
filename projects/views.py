from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _

from offers.forms import CreateOfferForm
from offers.models import Offer
from projects.forms import (
    ProjectSearchForm, StoryForm, EstimationForm)
from projects.models import Project
from stories.models import Story
from tools.views import ListView, CreateView, UpdateView


class ProjectListView(ListView):
    model = Project
    search_form_class = ProjectSearchForm

    def get_queryset(self):
        return super().get_queryset().select_related(
            'customer',
            'contact__organization',
        )


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
                _("%(class)s '%(object)s' has been successfully created.") % {
                    'class': story._meta.verbose_name,
                    'object': story,
                })

            if '_continue' in request.POST:
                return redirect('.')
            else:
                return HttpResponse('Thanks', status=201)  # Created

        return self.render_to_response(self.get_context_data(form=form))


class OfferCreateView(CreateView):
    model = Offer

    def allow_create(self):
        self.project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return True

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'owned_by': self.request.user.id,
        })
        return CreateOfferForm(data, files, project=self.project, **kwargs)


class EstimationView(UpdateView):
    model = Project

    template_name_suffix = '_estimation'
    form_class = EstimationForm
