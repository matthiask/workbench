from django.utils.functional import cached_property

import vanilla


class ListView(vanilla.ListView):
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
