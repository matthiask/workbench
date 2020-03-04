from django.conf.urls import url

from workbench import generic
from workbench.accounts.features import controlling_only
from workbench.deals.forms import DealForm, DealSearchForm, SetStatusForm
from workbench.deals.models import Deal


urlpatterns = [
    url(
        r"^$",
        controlling_only(
            generic.ListView.as_view(
                model=Deal, search_form_class=DealSearchForm, paginate_by=None
            )
        ),
        name="deals_deal_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        controlling_only(generic.DetailView.as_view(model=Deal)),
        name="deals_deal_detail",
    ),
    url(
        r"^create/$",
        controlling_only(generic.CreateView.as_view(form_class=DealForm, model=Deal)),
        name="deals_deal_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        controlling_only(generic.UpdateView.as_view(form_class=DealForm, model=Deal)),
        name="deals_deal_update",
    ),
    url(
        r"^(?P<pk>\d+)/set-status/$",
        controlling_only(
            generic.UpdateView.as_view(
                form_class=SetStatusForm, model=Deal, template_name="modalform.html"
            )
        ),
        name="deals_deal_set_status",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        controlling_only(generic.DeleteView.as_view(model=Deal)),
        name="deals_deal_delete",
    ),
]
