from django.shortcuts import get_object_or_404, redirect

from workbench import generic
from workbench.projects.models import Project, Service


class CreateRelatedView(generic.CreateView):
    def get_form(self, data=None, files=None, **kwargs):
        self.project = get_object_or_404(Project, pk=self.kwargs.pop("pk"))
        return super().get_form(data, files, project=self.project, **kwargs)


class MoveServiceView(generic.DetailView):
    model = Service

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.model.allow_update(self.object, request):
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
