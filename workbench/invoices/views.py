from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import redirect
from django.utils.translation import ngettext

from workbench import generic
from workbench.invoices.models import Invoice, Service
from workbench.tools.models import Z
from workbench.tools.pdf import pdf_response


class InvoicePDFView(generic.DetailView):
    model = Invoice

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(self.object.code, as_attachment=False)

        pdf.init_invoice()
        pdf.process_invoice(self.object)
        pdf.generate()

        return response


class ServicesInvoiceUpdateView(generic.DetailView):
    model = Invoice
    template_name_suffix = "_services"

    def post(self, request, *args, **kwargs):
        print(request.POST)

        self.object = self.get_object()

        service = self.object.project.services.get(pk=request.POST["service"])
        Service.objects.filter(invoice=self.object, project_service=service).delete()

        invoice_service = Service.from_project_service(service, invoice=self.object)
        if request.POST["mode"] == "logbook":
            invoice_service.effort_hours = (
                service.loggedhours.order_by().aggregate(Sum("hours"))["hours__sum"]
                or Z
            )
        invoice_service.save()
        return redirect(".")


class RecurringInvoiceDetailView(generic.DetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get("create_invoices"):
            invoices = self.object.create_invoices(
                generate_until=date.today() + timedelta(days=20)
            )
            messages.info(
                request,
                ngettext("Created %s invoice", "Created %s invoices", len(invoices))
                % len(invoices),
            )
            return redirect("invoices_invoice_list" if len(invoices) else self.object)
        context = self.get_context_data()
        return self.render_to_response(context)


class RecurringInvoiceCreateView(generic.CreateView):
    def get_success_url(self):
        return self.object.urls.url("update")
