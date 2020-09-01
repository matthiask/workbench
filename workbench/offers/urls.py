from django.shortcuts import get_object_or_404, redirect
from django.urls import re_path

from workbench import generic
from workbench.accounts.features import controlling_only
from workbench.offers.forms import OfferForm, OfferPricingForm, OfferSearchForm
from workbench.offers.models import Offer
from workbench.offers.views import OfferDeleteView, OfferPDFView, copy_offer


urlpatterns = [
    re_path(
        r"^$",
        controlling_only(
            generic.ListView.as_view(model=Offer, search_form_class=OfferSearchForm)
        ),
        name="offers_offer_list",
    ),
    re_path(
        r"^autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Offer,
            queryset=Offer.objects.select_related("owned_by", "project"),
        ),
        name="offers_offer_autocomplete",
    ),
    re_path(
        r"^(?P<pk>\d+)/$",
        lambda request, pk: redirect(get_object_or_404(Offer, pk=pk)),
        name="offers_offer_detail",
    ),
    re_path(
        r"^create/$",
        controlling_only(generic.CreateView.as_view(model=Offer, form_class=OfferForm)),
        name="offers_offer_create",
    ),
    re_path(
        r"^(?P<pk>\d+)/update/$",
        controlling_only(generic.UpdateView.as_view(form_class=OfferForm, model=Offer)),
        name="offers_offer_update",
    ),
    re_path(
        r"^(?P<pk>\d+)/pricing/$",
        controlling_only(
            generic.UpdateView.as_view(
                form_class=OfferPricingForm,
                model=Offer,
                template_name_suffix="_pricing",
            )
        ),
        name="offers_offer_pricing",
    ),
    re_path(
        r"^(?P<pk>\d+)/delete/$",
        controlling_only(OfferDeleteView.as_view(model=Offer)),
        name="offers_offer_delete",
    ),
    re_path(
        r"^(?P<pk>\d+)/pdf/$",
        controlling_only(OfferPDFView.as_view()),
        name="offers_offer_pdf",
    ),
    re_path(
        r"^(?P<pk>\d+)/copy/$", controlling_only(copy_offer), name="offers_offer_copy"
    ),
]
