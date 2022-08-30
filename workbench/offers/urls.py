from django.shortcuts import get_object_or_404, redirect
from django.urls import path

from workbench import generic
from workbench.accounts.features import controlling_only
from workbench.offers.forms import OfferForm, OfferPricingForm, OfferSearchForm
from workbench.offers.models import Offer
from workbench.offers.views import OfferDeleteView, OfferPDFView, copy_offer


urlpatterns = [
    path(
        "",
        controlling_only(
            generic.ListView.as_view(model=Offer, search_form_class=OfferSearchForm)
        ),
        name="offers_offer_list",
    ),
    path(
        "autocomplete/",
        generic.AutocompleteView.as_view(
            model=Offer,
            queryset=Offer.objects.select_related("owned_by", "project"),
        ),
        name="offers_offer_autocomplete",
    ),
    path(
        "<int:pk>/",
        lambda request, pk: redirect(get_object_or_404(Offer, pk=pk)),
        name="offers_offer_detail",
    ),
    path(
        "create/",
        controlling_only(generic.CreateView.as_view(model=Offer, form_class=OfferForm)),
        name="offers_offer_create",
    ),
    path(
        "<int:pk>/update/",
        controlling_only(generic.UpdateView.as_view(form_class=OfferForm, model=Offer)),
        name="offers_offer_update",
    ),
    path(
        "<int:pk>/pricing/",
        controlling_only(
            generic.UpdateView.as_view(
                form_class=OfferPricingForm,
                model=Offer,
                template_name_suffix="_pricing",
            )
        ),
        name="offers_offer_pricing",
    ),
    path(
        "<int:pk>/delete/",
        controlling_only(OfferDeleteView.as_view(model=Offer)),
        name="offers_offer_delete",
    ),
    path(
        "<int:pk>/pdf/",
        controlling_only(OfferPDFView.as_view()),
        name="offers_offer_pdf",
    ),
    path("<int:pk>/copy/", controlling_only(copy_offer), name="offers_offer_copy"),
]
