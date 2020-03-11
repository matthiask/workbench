from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from workbench.deals.models import Deal
from workbench.offers.forms import OfferAutocompleteForm


def add_offer(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    form = OfferAutocompleteForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        offer = form.cleaned_data["offer"]
        deal.related_offers.add(offer)
        messages.success(
            request,
            _("Successfully added the offer %(offer)s as a related offer.")
            % {"offer": offer},
        )
        return HttpResponse("OK", status=201)

    return render(
        request,
        "generic/select_object.html",
        {"form": form, "title": _("Link offer to %(deal)s") % {"deal": deal}},
    )


@require_POST
def remove_offer(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    form = OfferAutocompleteForm(request.POST)
    if form.is_valid():
        offer = form.cleaned_data["offer"]
        deal.related_offers.remove(offer)
        messages.success(
            request,
            _("Successfully removed the offer %(offer)s as a related offer.")
            % {"offer": offer},
        )
    return redirect(deal)
