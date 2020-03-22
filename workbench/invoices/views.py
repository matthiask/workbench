import datetime as dt
from collections import defaultdict

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext, ngettext
from django.views.decorators.http import require_POST

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
            invoices = self.object.create_invoices()
            messages.info(
                request,
                ngettext("Created %s invoice.", "Created %s invoices.", len(invoices))
                % len(invoices),
            )
            return redirect("invoices_invoice_list" if len(invoices) else self.object)
        context = self.get_context_data()
        return self.render_to_response(context)


def reminders(request):
    invoices = Invoice.objects.overdue().select_related(
        "customer", "owned_by", "project"
    )
    by_organization = {}
    for invoice in invoices:
        if invoice.customer not in by_organization:
            by_organization[invoice.customer] = {
                "organization": invoice.customer,
                "last_reminded_on": {invoice.last_reminded_on},
                "invoices": [invoice],
            }
        else:
            row = by_organization[invoice.customer]
            row["invoices"].append(invoice)
            row["last_reminded_on"].add(invoice.last_reminded_on)

    def last_reminded_on(row):
        days = row["last_reminded_on"] - {None}
        return max(days) if days else None

    reminders = [
        dict(row, last_reminded_on=last_reminded_on(row))
        for row in by_organization.values()
    ]

    return render(
        request,
        "invoices/reminders.html",
        {
            "reminders": sorted(
                reminders,
                key=lambda row: (
                    row["last_reminded_on"] or dt.date.min,
                    row["organization"].name,
                ),
            )
        },
    )


@require_POST
def dunning_letter(request, customer_id):
    invoices = (
        Invoice.objects.overdue()
        .filter(customer=customer_id)
        .select_related("customer", "contact__organization", "owned_by", "project")
    )

    pdf, response = pdf_response("reminders", as_attachment=True)
    pdf.dunning_letter(invoices=list(invoices))
    pdf.generate()

    invoices.update(last_reminded_on=dt.date.today())

    return response
