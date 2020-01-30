import datetime as dt
from collections import defaultdict

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext, ngettext

from workbench import generic
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.tools.pdf import pdf_response
from workbench.tools.xlsx import WorkbenchXLSXDocument


class InvoicePDFView(generic.DetailView):
    model = Invoice

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(
            self.object.code,
            as_attachment=request.GET.get("disposition") == "attachment",
        )

        pdf.init_letter()
        pdf.process_invoice(self.object)
        pdf.generate()

        return response


class InvoiceXLSXView(generic.DetailView):
    model = Invoice

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        data = [
            [
                gettext("service"),
                gettext("description"),
                gettext("rendered on"),
                gettext("effort type"),
                gettext("hourly rate"),
                gettext("hours"),
                gettext("cost"),
            ],
            [],
        ]

        hours = defaultdict(list)
        cost = defaultdict(list)

        for entry in LoggedHours.objects.filter(invoice_service__invoice=self.object):
            hours[entry.invoice_service_id].append(entry)
        for entry in LoggedCost.objects.filter(invoice_service__invoice=self.object):
            cost[entry.invoice_service_id].append(entry)

        for service in self.object.services.all():
            data.append(
                [
                    service.title,
                    service.description,
                    "",
                    service.effort_type,
                    service.effort_rate,
                    "",
                    "",
                ]
            )
            for entry in hours[service.id]:
                data.append(
                    [
                        "",
                        entry.description,
                        entry.rendered_on,
                        "",
                        "",
                        entry.hours,
                        entry.hours * service.effort_rate
                        if service.effort_rate
                        else "",
                    ]
                )
            for entry in cost[service.id]:
                data.append(
                    ["", entry.description, entry.rendered_on, "", "", "", entry.cost]
                )
            data.append([])

        xlsx = WorkbenchXLSXDocument()
        xlsx.add_sheet(gettext("logbook"))
        xlsx.table(None, data)
        return xlsx.to_response("%s.xlsx" % self.object.code)


class RecurringInvoiceDetailView(generic.DetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get("create_invoices"):
            invoices = self.object.create_invoices(generate_until=dt.date.today())
            messages.info(
                request,
                ngettext("Created %s invoice.", "Created %s invoices.", len(invoices))
                % len(invoices),
            )
            return redirect("invoices_invoice_list" if len(invoices) else self.object)
        context = self.get_context_data()
        return self.render_to_response(context)
