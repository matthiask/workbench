from projects.forms import ProjectForm
from projects.models import Project
from tools.views import ListView, DetailView, CreateView


class ProjectViewMixin(object):
    model = Project


class ProjectListView(ProjectViewMixin, ListView):
    pass


class ProjectDetailView(ProjectViewMixin, DetailView):
    pass


class ProjectCreateView(ProjectViewMixin, CreateView):
    form_class = ProjectForm
