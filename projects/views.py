from django.utils.functional import cached_property

import vanilla

from projects.models import Project


class ProjectViewMixin(object):
    model = Project

    def get_queryset(self):
        return self.model.objects.all()


class ProjectListView(ProjectViewMixin, vanilla.ListView):
    model = Project

    def get_queryset(self):
        self.root_queryset = queryset = self.model.objects.all()

        q = self.request.GET.get('q')
        self.queryset = queryset.search(q) if q else queryset
        return self.queryset

    @cached_property
    def counts(self):
        return {
            'root': self.root_queryset.count(),
            'search': self.queryset.count(),
        }


class ProjectDetailView(ProjectViewMixin, vanilla.DetailView):
    pass
