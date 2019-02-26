from collections import namedtuple
import itertools

from django.shortcuts import get_object_or_404

from workbench.offers.models import Service
from workbench.projects.models import Project
from workbench.generic import ListView, DetailView, CreateView


class CreateRelatedView(CreateView):
    def get_form(self, data=None, files=None, **kwargs):
        self.project = get_object_or_404(Project, pk=self.kwargs.pop("pk"))
        return super().get_form(data, files, project=self.project, **kwargs)


ServiceCosts = namedtuple("ServiceCosts", "service offered logged costs")


class CostView(object):
    def __init__(self, project):
        self.project = project

        self.costs = self.project.loggedcosts.order_by(
            "service", "rendered_on"
        ).select_related("created_by")

        self.services = {}
        for key, group in itertools.groupby(self.costs, lambda cost: cost.service_id):
            group = list(group)
            self.services[key] = list(group)

    def __iter__(self):
        if None in self.services:
            yield ServiceCosts(
                None,
                0,
                sum((c.cost for c in self.services[None]), 0),
                self.services[None],
            )

        for service in Service.objects.filter(
            offer__project=self.project
        ).prefetch_related("costs"):
            if service.id in self.services or service.costs.all():
                entries = self.services.get(service.id, [])
                yield ServiceCosts(
                    service,
                    sum((c.cost for c in service.costs.all()), 0),
                    sum((c.cost for c in entries), 0),
                    entries,
                )


class ProjectDetailView(DetailView):
    model = Project
    project_view = None

    def get_context_data(self, **kwargs):
        if self.project_view == "costs":
            kwargs["costs"] = CostView(self.object)

        return super().get_context_data(**kwargs)


class ServiceListView(ListView):
    template_name = "projects/project_service_list.html"
    paginate_by = None

    def get_root_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["pk"])
        return self.model.objects.filter(offer__project=self.project)
