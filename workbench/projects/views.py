from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _

from workbench import generic
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service


class CreateRelatedView(generic.CreateView):
    def get_form(self, data=None, files=None, **kwargs):
        self.project = get_object_or_404(Project, pk=self.kwargs.pop("pk"))
        return super().get_form(data, files, project=self.project, **kwargs)


class ProjectDetailView(generic.DetailView):
    model = Project
    project_view = None

    def get_template_names(self):
        return "projects/project_detail_%s.html" % self.project_view


class MoveServiceView(generic.DetailView):
    model = Service

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.model.allow_update(self.object, request):
            return redirect(self.object.offer)
        if self.object.offer and self.object.offer.status > Offer.IN_PREPARATION:
            messages.error(
                request,
                _("Cannot modify an offer which is not in preparation anymore."),
            )
            return redirect(self.object.offer)

        if self.object.offer:
            pks = list(self.object.offer.services.values_list("id", flat=True))
        else:
            pks = list(
                self.object.project.services.filter(offer=None).values_list(
                    "id", flat=True
                )
            )
        index = pks.index(self.object.pk)
        if "up" in request.GET and index > 0:
            pks[index], pks[index - 1] = pks[index - 1], pks[index]
        elif "down" in request.GET and index < len(pks) - 1:
            pks[index], pks[index + 1] = pks[index + 1], pks[index]

        for index, pk in enumerate(pks):
            Service.objects.filter(pk=pk).update(position=(index + 1) * 10)

        return redirect(self.object.project.urls.url("services"))
