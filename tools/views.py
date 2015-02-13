from django.utils.functional import cached_property

import vanilla


class ListView(vanilla.ListView):
    paginate_by = 10

    def get_queryset(self):
        self.root_queryset = self.model.objects.all()

        q = self.request.GET.get('q')
        return self.root_queryset.search(q) if q else self.root_queryset.all()

    @cached_property
    def root_queryset_count(self):
        return self.root_queryset.count()
