from django.conf.urls import url

from workbench import generic
from workbench.deals.forms import DealSearchForm, DealForm
from workbench.deals.models import Deal


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=Deal, search_form_class=DealSearchForm),
        name="deals_deal_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Deal),
        name="deals_deal_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(form_class=DealForm, model=Deal),
        name="deals_deal_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=DealForm, model=Deal),
        name="deals_deal_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Deal),
        name="deals_deal_delete",
    ),
]
