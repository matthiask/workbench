import io
import zipfile

from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import activate, gettext as _

from workbench.credit_control.models import CreditEntry, Ledger
from workbench.invoices.models import Invoice
from workbench.tools.pdf import PDFDocument
from workbench.tools.xlsx import WorkbenchXLSXDocument


def append_invoice(*, zf, ledger_slug, invoice):
    with io.BytesIO() as buf:
        pdf = PDFDocument(buf)
        pdf.init_letter()
        pdf.process_invoice(invoice)
        pdf.generate()

        zf.writestr(
            "%s-%s/%s.pdf"
            % (ledger_slug, invoice.closed_on.strftime("%Y.%m"), invoice.code),
            buf.getvalue(),
        )


def paid_debtors_zip(date_range, *, file):
    activate(settings.WORKBENCH.PDF_LANGUAGE)
    xlsx = WorkbenchXLSXDocument()

    with zipfile.ZipFile(file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for ledger in Ledger.objects.all():
            rows = []
            for entry in (
                CreditEntry.objects.filter(ledger=ledger, value_date__range=date_range)
                .order_by("value_date")
                .select_related("invoice__project", "invoice__owned_by")
            ):
                rows.append(
                    (
                        entry.value_date,
                        entry.total,
                        entry.payment_notice,
                        entry.invoice,
                        entry.notes,
                    )
                )

                if entry.invoice:
                    append_invoice(
                        zf=zf,
                        ledger_slug=slugify(ledger.name),
                        invoice=entry.invoice,
                    )

            xlsx.add_sheet(slugify(ledger.name))
            xlsx.table(
                (
                    _("value date"),
                    _("total"),
                    _("payment notice"),
                    _("invoice"),
                    _("notes"),
                ),
                rows,
            )

        rows = []
        for invoice in (
            Invoice.objects.filter(closed_on__range=date_range, status=Invoice.PAID)
            .exclude(
                pk__in=CreditEntry.objects.filter(invoice__isnull=False).values(
                    "invoice"
                )
            )
            .order_by("closed_on")
            .select_related("project")
        ):
            rows.append(
                (invoice.closed_on, invoice.total, invoice.payment_notice, invoice)
            )

            append_invoice(zf=zf, ledger_slug="unknown", invoice=invoice)

        xlsx.add_sheet("unknown")
        xlsx.table(
            (_("closed on"), _("total"), _("payment notice"), _("invoice")), rows
        )

        with io.BytesIO() as buf:
            xlsx.workbook.save(buf)
            zf.writestr("debtors.xlsx", buf.getvalue())
