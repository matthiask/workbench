from django.shortcuts import get_object_or_404

from offers.forms import CreateOfferForm
from offers.models import Offer
from projects.forms import EstimationForm
from projects.models import Project
from stories.forms import StoryForm
from stories.models import Story
from tools.views import CreateView, UpdateView


class StoryCreateView(CreateView):
    model = Story

    def get_form(self, data=None, files=None, **kwargs):
        self.project = get_object_or_404(Project, pk=self.kwargs['pk'])
        return StoryForm(
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


class EstimationView(UpdateView):
    model = Project

    template_name_suffix = '_estimation'
    form_class = EstimationForm
