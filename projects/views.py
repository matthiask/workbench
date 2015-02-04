import vanilla

from projects.models import Project


class ProjectViewMixin(object):
    model = Project

    def get_queryset(self):
        return self.model.objects.all()


class ProjectDetailView(ProjectViewMixin, vanilla.DetailView):
    pass
