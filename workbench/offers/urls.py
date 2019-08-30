from django.conf.urls import url

from workbench import generic
from workbench.offers.forms import OfferForm, OfferSearchForm
from workbench.offers.models import Offer
from workbench.offers.views import OfferPDFView, copy_offer


urlpatterns = [
    url(
        r"^$",
        generic.ListView.as_view(model=Offer, search_form_class=OfferSearchForm),
        name="offers_offer_list",
    ),
    url(
        r"^(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Offer),
        name="offers_offer_detail",
    ),
    url(
        r"^create/$",
        generic.CreateView.as_view(model=Offer, form_class=OfferForm),
        name="offers_offer_create",
    ),
    url(
        r"^(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=OfferForm, model=Offer),
        name="offers_offer_update",
    ),
    url(
        r"^(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Offer),
        name="offers_offer_delete",
    ),
    url(r"^(?P<pk>\d+)/pdf/$", OfferPDFView.as_view(), name="offers_offer_pdf"),
    url(r"^(?P<pk>\d+)/copy/$", copy_offer, name="offers_offer_copy"),
]
