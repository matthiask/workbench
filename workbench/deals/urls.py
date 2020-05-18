from django.urls import re_path

from workbench import generic
from workbench.accounts.features import deals_only
from workbench.deals import views
from workbench.deals.forms import DealForm, DealSearchForm, SetStatusForm
from workbench.deals.models import Deal


urlpatterns = [
    re_path(
        r"^$",
        deals_only(
            generic.ListView.as_view(
                model=Deal, search_form_class=DealSearchForm, paginate_by=None
            )
        ),
        name="deals_deal_list",
    ),
    re_path(
        r"^(?P<pk>\d+)/$",
        deals_only(generic.DetailView.as_view(model=Deal)),
        name="deals_deal_detail",
    ),
    re_path(
        r"^create/$",
        deals_only(generic.CreateView.as_view(form_class=DealForm, model=Deal)),
        name="deals_deal_create",
    ),
    re_path(
        r"^(?P<pk>\d+)/update/$",
        deals_only(generic.UpdateView.as_view(form_class=DealForm, model=Deal)),
        name="deals_deal_update",
    ),
    re_path(
        r"^(?P<pk>\d+)/set-status/$",
        deals_only(
            generic.UpdateView.as_view(
                form_class=SetStatusForm, model=Deal, template_name="modalform.html"
            )
        ),
        name="deals_deal_set_status",
    ),
    re_path(
        r"^(?P<pk>[0-9]+)/add-offer/$",
        deals_only(views.add_offer),
        name="deals_deal_add_offer",
    ),
    re_path(
        r"^(?P<pk>[0-9]+)/remove-offer/$",
        deals_only(views.remove_offer),
        name="deals_deal_remove_offer",
    ),
    re_path(
        r"^(?P<pk>\d+)/delete/$",
        deals_only(generic.DeleteView.as_view(model=Deal)),
        name="deals_deal_delete",
    ),
]
