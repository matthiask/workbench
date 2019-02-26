from django.conf.urls import url
from django.utils.translation import ugettext_lazy as _

from workbench.offers.forms import OfferSearchForm, OfferForm
from workbench.offers.models import Offer
from workbench.offers.views import OfferPDFView
from workbench.generic import ListView, DetailView, UpdateView, DeleteView, MessageView


urlpatterns = [
    url(
        r"^$",
        ListView.as_view(model=Offer, search_form_class=OfferSearchForm),
        name="offers_offer_list",
    ),
    url(r"^(?P<pk>\d+)/$", DetailView.as_view(model=Offer), name="offers_offer_detail"),
    url(
        r"^create/$",
        MessageView.as_view(
            redirect_to="projects_project_list",
            message=_(
                "Create a project, add and estimate services, and put those"
                " services into an offer."
            ),
        ),
        name="offers_offer_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        UpdateView.as_view(form_class=OfferForm, model=Offer),
        name="offers_offer_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        DeleteView.as_view(model=Offer),
        name="offers_offer_delete",
    ),
    url(r"^(?P<pk>\d+)/pdf/$", OfferPDFView.as_view(), name="offers_offer_pdf"),
]
