from django.conf.urls import url
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext_lazy as _

from workbench.offers.forms import OfferSearchForm, OfferForm
from workbench.offers.models import Offer, Service
from workbench.offers.views import (
    OfferPDFView,
    CreateServiceView,
    UpdateServiceView,
    DeleteServiceView,
    MoveServiceView,
)
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
    url(
        r"^(?P<pk>\d+)/createservice/$",
        CreateServiceView.as_view(),
        name="offers_offer_createservice",
    ),
    url(
        r"^service/(?P<pk>\d+)/$",
        lambda request, pk: redirect(get_object_or_404(Service, pk=pk).offer),
        name="offers_service_detail",
    ),
    url(
        r"^service/(?P<pk>\d+)/update/$",
        UpdateServiceView.as_view(),
        name="offers_service_update",
    ),
    url(
        r"^service/(?P<pk>\d+)/delete/$",
        DeleteServiceView.as_view(),
        name="offers_service_delete",
    ),
    url(
        r"^service/(?P<pk>\d+)/move/$",
        MoveServiceView.as_view(),
        name="offers_service_move",
    ),
    url(r"^(?P<pk>\d+)/pdf/$", OfferPDFView.as_view(), name="offers_offer_pdf"),
]
