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

        pdf.init_letter()

        pdf.p(o.postal_address)
        pdf.next_frame()

        pdf.small(o.offered_on.strftime('%A %d.%m.%Y'))
        pdf.h1(o.title)
        pdf.p(o.description)
        pdf.spacer()

        pdf.table_stories(o.story_data['stories'])
        pdf.table_total(o)

        pdf.spacer()
        pdf.smaller(
            'Die zum Zeitpunkt des Vertragsabschlusses aktuellen AGB der'
            ' FEINHEIT GmbH sind integraler Bestandteil dieser Offerte.'
            ' Sie finden die jeweils aktuelle Version auf'
            ' www.feinheit.ch/agb/.')

        pdf.smaller(
            'Bestandteil dieser Offerte sind die zum Zeitpunkt des'
            ' Vertragsabschlusses aktuellen Allgemeinen Geschäftsbedingungen'
            ' der FEINHEIT GmbH. Sie finden die jeweils aktuelle Version der'
            ' AGB auf www.feinheit.ch/agb/. Mit der Annahme dieser Offerte'
            ' bestätigen Sie, dass Sie die AGB gelesen haben und diese als'
            ' Vertragsbestandteil akzeptieren.')

        pdf.generate()
        return response
