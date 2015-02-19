from projects.forms import ProjectSearchForm, ProjectForm
from projects.models import Project
from tools.views import ListView, DetailView, CreateView


class ProjectViewMixin(object):
    model = Project


class ProjectListView(ProjectViewMixin, ListView):
    def get_queryset(self):
        queryset = super().get_queryset()

        self.search_form = ProjectSearchForm(self.request.GET)
        if self.search_form.is_valid():
            data = self.search_form.cleaned_data
            if data.get('s'):
                queryset = queryset.filter(status=data.get('s'))

        return queryset


class ProjectDetailView(ProjectViewMixin, DetailView):
    pass


class ProjectCreateView(ProjectViewMixin, CreateView):
    form_class = ProjectForm
