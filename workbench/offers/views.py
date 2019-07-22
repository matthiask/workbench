from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from workbench.generic import DetailView
from workbench.offers.models import Offer
from workbench.projects.models import Project
from workbench.tools.pdf import pdf_response


class OfferPDFView(DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(self.object.code, as_attachment=False)

        pdf.init_letter()
        pdf.process_offer(self.object)
        pdf.generate()

        return response


class ProjectOfferPDFView(DetailView):
    model = Project

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        offers = list(self.object.offers.order_by("_code"))

        if not offers:
            messages.error(request, _("No offers in project."))
            return redirect(self.object)

        pdf, response = pdf_response(self.object.code, as_attachment=False)
        pdf.offers_pdf(offers=offers)

        return response
