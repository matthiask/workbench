from django.template.defaultfilters  import date as date_fmt

from offers.forms import OfferSearchForm
from offers.models import Offer
from tools.pdf import pdf_response
from tools.views import DetailView, ListView


class OfferListView(ListView):
    model = Offer
    search_form_class = OfferSearchForm

    def get_queryset(self):
        return super().get_queryset().select_related(
            'customer',
            'contact__organization',
        )


class OfferPDFView(DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = o = self.get_object()

        pdf, response = pdf_response(
            'offer-%d' % o.pk,
            as_attachment=False)

        pdf.init_offer()

        pdf.p(o.postal_address)
        pdf.next_frame()

        pdf.small(date_fmt(o.offered_on, 'l d.m.Y'))
        pdf.h1(o.title)
        pdf.p(o.description)
        pdf.spacer()

        pdf.table_stories(o.story_data['stories'])
        pdf.table_total(o)

        pdf.generate()
        return response
