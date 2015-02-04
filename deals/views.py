from collections import defaultdict

import vanilla

from deals.forms import DealSearchForm
from deals.models import Funnel, Deal


class FunnelViewMixin(object):
    model = Funnel

    def get_queryset(self):
        return self.model.objects.all()


class FunnelDetailView(FunnelViewMixin, vanilla.DetailView):
    def get_context_data(self, **kwargs):
        deals = defaultdict(list)
        for deal in self.object.deals.all():
            deals[deal.status].append(deal)

        return super().get_context_data(
            funnel_details=[
                {
                    'title': title,
                    'deals': deals.get(status, []),
                } for status, title in Deal.STATUS_CHOICES
            ], **kwargs)


class DealListView(vanilla.ListView):
    model = Deal

    def get_queryset(self):
        self.search_form = DealSearchForm(self.request.GET)
        queryset = self.model.objects.all()
        if self.search_form.is_valid():
            data = self.search_form.cleaned_data
            if data.get('f'):
                queryset = queryset.filter(funnel=data.get('f'))
        q = self.request.GET.get('q')
        return queryset.search(q) if q else queryset


class DealDetailView(vanilla.DetailView):
    model = Deal
