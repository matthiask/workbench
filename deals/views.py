from collections import defaultdict

import reversion

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


def changes(instance, fields):
    versions = reversion.get_for_object(instance)[::-1]
    changes = []
    for previous, update in zip(versions, versions[1:]):
        version_changes = []
        for field in fields:
            f = (
                instance._meta.get_field(field).verbose_name,
                previous.field_dict.get(field),
                update.field_dict.get(field),
            )

            if f[1] == f[2]:
                continue

            version_changes.append('"%s" changed from "%s" to "%s".' % f)

        changes.append(version_changes)
    return changes


class DealDetailView(DealViewMixin, DetailView):
    def get_context_data(self, **kwargs):
        return super().get_context_data(
            changes=changes(
                self.object,
                ('funnel', 'title', 'owned_by', 'estimated_value'),
            ), **kwargs)


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
