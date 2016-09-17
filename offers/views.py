from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _

from offers.forms import ServiceForm
from offers.models import Offer, Service
from tools.pdf import pdf_response
from tools.views import DetailView, CreateView


class OfferPDFView(DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(self.object.code, as_attachment=False)

        pdf.init_offer()
        pdf.process_offer(self.object)
        pdf.generate()

        return response


class CreateServiceView(CreateView):
    model = Service

    def get(self, request, *args, **kwargs):

        if not self.model.allow_create(request):
            return redirect('../')

        self.offer = get_object_or_404(Offer, pk=self.kwargs['pk'])
        if self.offer.status > Offer.IN_PREPARATION:
            messages.error(request, _(
                'Cannot modify an offer which is not in preparation anymore.'
            ))
            return redirect('../')

        form = self.get_form()
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_form(self, data=None, files=None, **kwargs):
        return ServiceForm(
            data,
            files,
            offer=self.offer,
            request=self.request,
            **kwargs)
