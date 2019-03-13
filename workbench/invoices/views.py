from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
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


class CreateRelatedView(generic.CreateView):
    def get_form(self, data=None, files=None, **kwargs):
        self.invoice = get_object_or_404(Invoice, pk=self.kwargs.pop("pk"))
        return super().get_form(data, files, invoice=self.invoice, **kwargs)


class ServicesInvoiceUpdateView(generic.DetailView):
    model = Invoice
    template_name_suffix = "_services"

    def get(self, request, *args, **kwargs):
        # TODO allow_update etc.
        if not request.GET:
            return super().get(request, *args, **kwargs)

        self.object = self.get_object()
        mode = request.GET.get("mode")

        if "service" in request.GET:
            service = self.object.project.services.get(pk=request.GET["service"])
            invoice_service = Service.objects.filter(
                invoice=self.object, project_service=service
            ).first()
            if not invoice_service:
                invoice_service = Service(
                    invoice=self.object,
                    project_service=service,
                    title=service.title,
                    description=service.description,
                    position=service.position,
                )

            if mode == "description":
                invoice_service.title = service.title
                invoice_service.description = service.description
                invoice_service.position = service.position
            elif mode == "service_hours":
                invoice_service.effort_type = service.effort_type
                invoice_service.effort_rate = service.effort_rate
                invoice_service.effort_hours = service.effort_hours
            elif mode == "logged_hours":
                invoice_service.effort_type = service.effort_type
                invoice_service.effort_rate = service.effort_rate
                invoice_service.effort_hours = (
                    service.loggedhours.order_by().aggregate(Sum("hours"))["hours__sum"]
                    or Z
                )
            elif mode == "service_cost":
                invoice_service.cost = service.cost
                invoice_service.third_party_costs = service.third_party_costs
            elif mode == "logged_cost":
                logged = service.loggedcosts.all()
                invoice_service.cost = sum((log.cost for log in logged), Z)
                invoice_service.third_party_costs = sum(
                    (log.third_party_costs or Z for log in logged), Z
                )

            invoice_service.save()

            # FIXME archival / assignment of services

        elif "invoice_service" in request.GET:
            service = self.object.services.get(pk=request.GET["invoice_service"])

            if mode == "remove":
                service.delete()

        self.object.save()

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
