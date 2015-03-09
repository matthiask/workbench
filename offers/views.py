
from offers.forms import OfferSearchForm
from offers.models import Offer
from tools.pdf import pdf_response, mm
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

        pdf.postal_address(o.postal_address)
        pdf.date_line(o.offered_on, short_name=o.owned_by.get_short_name())

        pdf.h1(o.title)
        pdf.spacer(2 * mm)

        pdf.p(o.description)
        pdf.spacer()

        pdf.table_stories(o.story_data['stories'])
        pdf.table_total(o)

        pdf.generate()
        return response
