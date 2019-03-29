from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import ngettext

from workbench import generic
from workbench.invoices.models import Invoice
from workbench.tools.pdf import pdf_response


class InvoicePDFView(generic.DetailView):
    model = Invoice

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(self.object.code, as_attachment=False)

        pdf.init_letter(page_fn=pdf.stationery())
        pdf.process_invoice(self.object)
        pdf.generate()

        return response


class RecurringInvoiceDetailView(generic.DetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get("create_invoices"):
            invoices = self.object.create_invoices(
                generate_until=date.today() + timedelta(days=20)
            )
            messages.info(
                request,
                ngettext("Created %s invoice.", "Created %s invoices.", len(invoices))
                % len(invoices),
            )
            return redirect("invoices_invoice_list" if len(invoices) else self.object)
        context = self.get_context_data()
        return self.render_to_response(context)
