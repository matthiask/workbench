import datetime as dt
from collections import defaultdict

from django.contrib import messages
from django.db.models import F
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.utils.translation import gettext, ngettext

from workbench import generic
from workbench.contacts.models import Person
from workbench.invoices.forms import SendReminderForm
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

        try:
            pdf.init_invoice_letter()
            pdf.process_invoice(self.object)
            pdf.generate()
        except Exception as exc:
            messages.error(
                request, gettext("Unable to generate the PDF: {}").format(exc)
            )
            return redirect(self.object)

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

        for entry in LoggedHours.objects.filter(
            invoice_service__invoice=self.object
        ).reverse():
            hours[entry.invoice_service_id].append(entry)
        for entry in LoggedCost.objects.filter(
            invoice_service__invoice=self.object
        ).reverse():
            cost[entry.invoice_service_id].append(entry)

        for service in self.object.services.all():
            data.append([
                service.title,
                service.description,
                "",
                service.effort_type,
                service.effort_rate,
                "",
                "",
            ])
            for entry in hours[service.id]:
                data.append([
                    "",
                    entry.description,
                    entry.rendered_on,
                    "",
                    "",
                    entry.hours,
                    entry.hours * service.effort_rate if service.effort_rate else "",
                ])
            for entry in cost[service.id]:
                data.append([
                    "",
                    entry.description,
                    entry.rendered_on,
                    "",
                    "",
                    "",
                    entry.cost,
                ])
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
    if request.method == "POST":
        Invoice.objects.filter(id__in=request.POST.getlist("invoice")).update(
            last_reminded_on=dt.date.today()
        )
        return HttpResponseRedirect(".")

    invoices = (
        Invoice.objects
        .overdue()
        .select_related("customer", "contact__organization", "owned_by", "project")
        # .order_by("customer", "contact")
        .order_by(F("last_reminded_on").asc(nulls_first=True), "invoiced_on")
    )

    nested = {}
    for invoice in invoices:
        nested.setdefault(invoice.customer, {}).setdefault(invoice.contact, []).append(
            invoice
        )

    return render(
        request,
        "invoices/reminders.html",
        {
            "nested": nested,
        },
    )


def dunning_letter(request, contact_id):
    if invoices := list(
        Invoice.objects
        .overdue()
        .filter(contact=contact_id)
        .select_related("customer", "contact__organization", "owned_by", "project")
    ):
        pdf, response = pdf_response(
            f"reminders-{slugify(invoices[0].contact.name_with_organization)}",
            as_attachment=True,
        )
        pdf.dunning_letter(invoices=invoices)
        pdf.generate()
        return response
    messages.error(request, gettext("No overdue invoices for this contact."))
    return redirect("invoices_reminders")


def send_reminder(request, contact_id):
    contact = get_object_or_404(Person, pk=contact_id)
    args = (request.POST,) if request.method == "POST" else ()
    form = SendReminderForm(*args, contact=contact, request=request)

    if form.is_valid():
        form.process()
        return HttpResponse("OK", status=202)

    return render(
        request,
        "invoices/send_reminder.html",
        {"form": form, "title": gettext("Send reminder")},
    )
