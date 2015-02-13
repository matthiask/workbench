import vanilla

from projects.models import Project
from tools.views import ListView


class ProjectViewMixin(object):
    model = Project

    def get_queryset(self):
        return self.model.objects.all()


class ProjectListView(ProjectViewMixin, ListView):
    model = Project


class ProjectDetailView(ProjectViewMixin, vanilla.DetailView):
    pass
