from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from workbench import generic
from workbench.offers.forms import OfferCopyForm, OfferDeleteForm
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.pdf import pdf_response


class OfferPDFView(generic.DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(
            self.object.code,
            as_attachment=request.GET.get("disposition") == "attachment",
        )

        pdf.init_letter()
        pdf.process_offer(self.object)
        pdf.generate()

        return response


class ProjectOfferPDFView(generic.DetailView):
    model = Project

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        offers = list(self.object.offers.order_by("_code"))

        if not offers:
            messages.error(request, _("No offers in project."))
            return redirect(self.object)

        pdf, response = pdf_response(
            self.object.code,
            as_attachment=request.GET.get("disposition") == "attachment",
        )
        pdf.offers_pdf(project=self.object, offers=offers)

        return response


class OfferDeleteView(generic.DeleteView):
    delete_form_class = OfferDeleteForm

    def get_success_url(self):
        return self.object.project.get_absolute_url()


def copy_offer(request, pk):
    offer = get_object_or_404(Offer, pk=pk)
    form = OfferCopyForm(
        request.POST if request.method == "POST" else None,
        project=offer.project,
        request=request,
    )
    if form.is_valid():
        new = offer.copy_to(project=form.cleaned_data["project"], owned_by=request.user)
        return JsonResponse({"redirect": new.get_absolute_url()}, status=299)
    return render(
        request,
        "generic/select_object.html",
        {"form": form, "title": _("Copy %s to project") % offer},
    )
