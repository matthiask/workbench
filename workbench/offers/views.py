from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext

from workbench import generic
from workbench.accounts.models import User
from workbench.audit.models import audit_user_id
from workbench.offers.forms import OfferCopyForm, OfferDeleteForm
from workbench.offers.history import YEARS, offer_states, state_by_event_id
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.pdf import offer_filename, offers_filename, pdf_response


class OfferPDFView(generic.DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(
            offer_filename(self.object),
            as_attachment=request.GET.get("disposition") == "attachment",
        )

        try:
            pdf.init_letter()
            pdf.process_offer(self.object)
            if request.GET.get("signature_line"):
                pdf.add_agreement(self.object)
            pdf.generate()
        except Exception as exc:  # noqa: BLE001
            messages.error(
                request, gettext("Unable to generate the PDF: {}").format(exc)
            )
            return redirect(self.object)

        return response


class ProjectOfferPDFView(generic.DetailView):
    model = Project

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        offers = list(self.object.offers.not_declined().order_by("_code"))

        if not offers:
            messages.error(request, gettext("No offers in project."))
            return redirect(self.object)

        pdf, response = pdf_response(
            offers_filename(self.object),
            as_attachment=request.GET.get("disposition") == "attachment",
        )
        pdf.offers_pdf(
            project=self.object,
            offers=offers,
            signature_line=request.GET.get("signature_line"),
        )

        return response


def offer_history(request, pk):
    """Earlier states of the project's offers, from the audit log"""
    project = get_object_or_404(Project, pk=pk)
    states = offer_states(project)
    users = User.objects.in_bulk({
        id for state in states if (id := audit_user_id(state.user_name))
    })
    return render(
        request,
        "projects/project_offer_history.html",
        {
            "object": project,
            "project": project,
            "years": YEARS,
            "states": [
                {
                    "state": state,
                    "user": users.get(audit_user_id(state.user_name))
                    or state.user_name,
                    "offers": [
                        {
                            "offer": offer,
                            "changed": offer.pk in state.changed_offer_ids,
                        }
                        for offer in state.offers(project)
                    ],
                }
                for state in states
            ],
        },
    )


def offer_history_pdf(request, pk, event_id):
    """The PDF of one or all offers of an earlier state"""
    project = get_object_or_404(Project, pk=pk)
    if not (state := state_by_event_id(project, event_id)):
        raise Http404
    offers = state.offers(project)
    as_attachment = request.GET.get("disposition") == "attachment"
    if offer_id := request.GET.get("offer"):
        offer = next((o for o in offers if str(o.pk) == offer_id), None)
        if offer is None:
            raise Http404
        pdf, response = pdf_response(offer_filename(offer), as_attachment=as_attachment)
        pdf.init_letter()
        pdf.process_offer(offer, items=offer.history_items, version=state.created_at)
        pdf.generate()
        return response

    offers = [offer for offer in offers if offer.status not in Offer.NOT_PURSUED]
    if not offers:
        messages.error(request, gettext("No offers in project."))
        return redirect(project.urls["offer_history"])
    pdf, response = pdf_response(offers_filename(project), as_attachment=as_attachment)
    pdf.offers_pdf(project=project, offers=offers, version=state.created_at)
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
        {"form": form, "title": gettext("Copy %s to project") % offer},
    )
