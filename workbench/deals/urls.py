from django.urls import path

from workbench import generic
from workbench.accounts.features import deals_only
from workbench.deals import views
from workbench.deals.forms import DealForm, DealSearchForm, SetStatusForm
from workbench.deals.models import Deal


urlpatterns = [
    path(
        "",
        deals_only(
            generic.ListView.as_view(
                model=Deal, search_form_class=DealSearchForm, paginate_by=None
            )
        ),
        name="deals_deal_list",
    ),
    path(
        "<int:pk>/",
        deals_only(generic.DetailView.as_view(model=Deal)),
        name="deals_deal_detail",
    ),
    path(
        "create/",
        deals_only(generic.CreateView.as_view(form_class=DealForm, model=Deal)),
        name="deals_deal_create",
    ),
    path(
        "<int:pk>/update/",
        deals_only(generic.UpdateView.as_view(form_class=DealForm, model=Deal)),
        name="deals_deal_update",
    ),
    path(
        "<int:pk>/set-status/",
        deals_only(
            generic.UpdateView.as_view(
                form_class=SetStatusForm, model=Deal, template_name="modalform.html"
            )
        ),
        name="deals_deal_set_status",
    ),
    path(
        "<int:pk>/add-offer/",
        deals_only(views.add_offer),
        name="deals_deal_add_offer",
    ),
    path(
        "<int:pk>/remove-offer/",
        deals_only(views.remove_offer),
        name="deals_deal_remove_offer",
    ),
    path(
        "<int:pk>/delete/",
        deals_only(generic.DeleteView.as_view(model=Deal)),
        name="deals_deal_delete",
    ),
]
