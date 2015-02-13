import vanilla

from projects.models import Project
from tools.views import ListView


class ProjectViewMixin(object):
    model = Project


class ProjectListView(ProjectViewMixin, ListView):
    model = Project


class ProjectDetailView(ProjectViewMixin, vanilla.DetailView):
    pass
