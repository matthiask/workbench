from collections import defaultdict

from deals.forms import DealSearchForm
from deals.models import Funnel, Deal
from tools.views import ListView, DetailView, CreateView, UpdateView


class FunnelViewMixin(object):
    model = Funnel


class DealViewMixin(object):
    model = Deal


class FunnelDetailView(FunnelViewMixin, DetailView):
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


class DealListView(DealViewMixin, ListView):
    def get_queryset(self):
        queryset = super().get_queryset()

        self.search_form = DealSearchForm(self.request.GET)
        if self.search_form.is_valid():
            data = self.search_form.cleaned_data
            if data.get('f'):
                queryset = queryset.filter(funnel=data.get('f'))

        return queryset


class DealDetailView(DealViewMixin, DetailView):
    pass


class DealCreateView(DealViewMixin, CreateView):
    fields = (
        'funnel', 'title', 'description', 'owned_by', 'estimated_value')

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'owned_by': self.request.user.pk,
        })
        form_class = self.get_form_class()
        return form_class(data, files, **kwargs)


class DealUpdateView(DealViewMixin, UpdateView):
    fields = (
        'funnel', 'title', 'description', 'owned_by', 'estimated_value')
