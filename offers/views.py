from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from offers.forms import OfferSearchForm
from offers.models import Offer
from tools.pdf import pdf_response
from tools.views import DetailView, ListView


class OfferListView(ListView):
    model = Offer
    search_form_class = OfferSearchForm

    def get_queryset(self):
        return super().get_queryset().select_related(
            'project__customer',
            'project__contact__organization',
        )


class OfferRefreshView(DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.refresh()
        messages.success(
            self.request,
            _('Successfully refreshed the offer.'))
        return redirect(self.object)


class OfferPDFView(DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(
            'offer-%d' % self.object.pk,
            as_attachment=False)

        pdf.init_offer()
        pdf.process_offer(self.object)
        pdf.generate()

        return response
