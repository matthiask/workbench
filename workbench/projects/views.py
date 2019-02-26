from collections import namedtuple
import itertools

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _

from workbench.offers.models import Offer
from workbench.projects.forms import ServiceForm
from workbench.projects.models import Project, Service
from workbench.generic import ListView, DetailView, CreateView, UpdateView, DeleteView


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


class CreateServiceView(CreateView):
    model = Service

    def get(self, request, *args, **kwargs):
        if not self.model.allow_create(request):
            return redirect("../")

        self.project = get_object_or_404(Project, pk=self.kwargs["pk"])
        form = self.get_form()
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_form(self, data=None, files=None, **kwargs):
        if not hasattr(self, "project"):
            self.project = get_object_or_404(Project, pk=self.kwargs["pk"])
        return ServiceForm(
            data, files, project=self.project, request=self.request, **kwargs
        )

    def get_success_url(self):
        return self.object.urls.url("update")


class UpdateServiceView(UpdateView):
    model = Service
    form_class = ServiceForm

    def get_success_url(self):
        return self.object.offer.get_absolute_url()


class DeleteServiceView(DeleteView):
    model = Service

    def get_success_url(self):
        return self.object.offer.get_absolute_url()


class MoveServiceView(DetailView):
    model = Service

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.model.allow_update(self.object, request):
            return redirect(self.object.offer)
        if self.object.offer.status > Offer.IN_PREPARATION:
            messages.error(
                request,
                _("Cannot modify an offer which is not in preparation anymore."),
            )
            return redirect(self.object.offer)

        pks = list(self.object.offer.services.values_list("id", flat=True))
        index = pks.index(self.object.pk)
        if "up" in request.GET and index > 0:
            pks[index], pks[index - 1] = pks[index - 1], pks[index]
        elif "down" in request.GET and index < len(pks) - 1:
            pks[index], pks[index + 1] = pks[index + 1], pks[index]

        for index, pk in enumerate(pks):
            Service.objects.filter(pk=pk).update(position=(index + 1) * 10)

        return redirect(self.object.offer)
