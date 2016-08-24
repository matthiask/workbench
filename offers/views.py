from offers.models import Offer
from tools.pdf import pdf_response
from tools.views import DetailView


class OfferPDFView(DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(self.object.code, as_attachment=False)

        pdf.init_offer()
        pdf.process_offer(self.object)
        pdf.generate()

        return response
