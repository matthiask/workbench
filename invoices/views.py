from invoices.models import Invoice
from tools.pdf import pdf_response
from tools.views import DetailView


class InvoicePDFView(DetailView):
    model = Invoice

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(
            'invoice-%d' % self.object.pk,
            as_attachment=False)

        pdf.init_invoice()
        pdf.process_invoice(self.object)
        pdf.generate()

        return response
