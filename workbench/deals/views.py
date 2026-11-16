from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from workbench.deals.forms import RelatedOfferForm, RelatedProjectForm
from workbench.deals.models import Deal


def add_offer(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    form = RelatedOfferForm(
        request.POST if request.method == "POST" else None, deal=deal, request=request
    )
    if form.is_valid():
        offer = form.save()
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
    form = RelatedOfferForm(request.POST, deal=deal, remove=True, request=request)
    if form.is_valid():
        offer = form.save()
        messages.success(
            request,
            _("Successfully removed the offer %(offer)s as a related offer.")
            % {"offer": offer},
        )
    else:
        for error in form.errors.values():
            messages.error(request, " ".join(error))
    return redirect(deal)


def add_project(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    form = RelatedProjectForm(
        request.POST if request.method == "POST" else None, deal=deal, request=request
    )
    if form.is_valid():
        project = form.save()
        messages.success(
            request,
            _("Successfully linked the project %(project)s.") % {"project": project},
        )
        return HttpResponse("OK", status=201)

    return render(
        request,
        "generic/select_object.html",
        {"form": form, "title": _("Link project to %(deal)s") % {"deal": deal}},
    )


@require_POST
def remove_project(request, pk):
    deal = get_object_or_404(Deal, pk=pk)
    form = RelatedProjectForm(request.POST, deal=deal, remove=True, request=request)
    if form.is_valid():
        project = form.save()
        messages.success(
            request,
            _("Successfully unlinked the project %(project)s.") % {"project": project},
        )
    else:
        for error in form.errors.values():
            messages.error(request, " ".join(error))
    return redirect(deal)
