import io
import zipfile

from django.conf import settings
from django.utils.translation import activate, gettext as _

from workbench.credit_control.models import CreditEntry
from workbench.invoices.models import Invoice
from workbench.tools.pdf import PDFDocument
from workbench.tools.xlsx import WorkbenchXLSXDocument


def append_invoice(*, zf, invoice, qr):
    with io.BytesIO() as buf:
        pdf = PDFDocument(buf)
        pdf.init_invoice_letter()
        pdf.process_invoice(invoice, qr=qr)
        try:
            pdf.generate()
        except Exception:
            print(f"Error while processing invoice {invoice} (ID {invoice.id})")
            raise

        zf.writestr(
            "{}/{}.pdf".format(invoice.invoiced_on.strftime("%Y.%m"), invoice.code),
            buf.getvalue(),
        )


def paid_debtors_zip(date_range, *, file, qr=False):
    activate(settings.WORKBENCH.PDF_LANGUAGE)
    xlsx = WorkbenchXLSXDocument()

    invoices = (
        Invoice.objects.filter(invoiced_on__range=date_range)
        .exclude(status=Invoice.IN_PREPARATION)
        .order_by("invoiced_on", "id")
        .select_related("project", "owned_by")
    )
    credit_entries = {
        ce.invoice_id: ce for ce in CreditEntry.objects.filter(invoice__in=invoices)
    }

    with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        rows = []
        for invoice in invoices:
            append_invoice(zf=zf, invoice=invoice, qr=qr)
            rows.append([
                invoice.code,
                invoice.invoiced_on,
                invoice.title,
                invoice.owned_by.get_short_name(),
                invoice.total_excl_tax,
                invoice.total,
                invoice.get_status_display(),
                invoice.closed_on,
                invoice.payment_notice,
            ])

            if entry := credit_entries.get(invoice.id):
                rows[-1].extend([
                    entry.value_date,
                    entry.total,
                    entry.payment_notice,
                    entry.notes,
                ])

        xlsx.add_sheet(_("invoices"))
        xlsx.table(
            (
                _("code"),
                _("invoiced on"),
                _("title"),
                _("contact person"),
                _("total excl. tax"),
                _("total"),
                _("status"),
                _("closed on"),
                _("payment notice"),
                _("value date"),
                _("total"),
                _("payment notice"),
                _("notes"),
            ),
            rows,
        )

        xlsx.add_sheet(_("Canceled"))
        xlsx.table(
            (
                _("code"),
                _("invoiced on"),
                _("title"),
                _("contact person"),
                _("total excl. tax"),
                _("total"),
                _("status"),
                _("closed on"),
                _("payment notice"),
            ),
            [
                (
                    invoice.code,
                    invoice.invoiced_on,
                    invoice.title,
                    invoice.owned_by.get_short_name(),
                    invoice.total_excl_tax,
                    invoice.total,
                    invoice.get_status_display(),
                    invoice.closed_on,
                    invoice.payment_notice,
                )
                for invoice in Invoice.objects.filter(status=Invoice.CANCELED)
                .order_by("closed_on", "id")
                .select_related("project", "owned_by")
            ],
        )

        with io.BytesIO() as buf:
            xlsx.workbook.save(buf)
            zf.writestr("debtors.xlsx", buf.getvalue())
