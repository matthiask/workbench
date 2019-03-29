from copy import deepcopy
from datetime import timedelta
from decimal import Decimal as D
from functools import partial

from django.conf import settings
from django.utils.translation import gettext as _

from pdfdocument.document import (
    Frame,
    MarkupParagraph,
    NextPageTemplate,
    PageTemplate,
    PDFDocument as _PDFDocument,
    cm,
    colors,
    getSampleStyleSheet,
    mm,
    register_fonts_from_paths,
    sanitize,
)
from pdfdocument.utils import pdf_response as _pdf_response

from workbench.tools.formats import currency, local_date_format


register_fonts_from_paths(font_name="Rep", **settings.WORKBENCH.FONTS)


Z = D("0.00")


class Empty(object):
    pass


def style(base, **kwargs):
    style = deepcopy(base)
    for key, value in kwargs.items():
        setattr(style, key, value)
    return style


class PDFDocument(_PDFDocument):
    def generate_style(self, *args, **kwargs):
        self.style = Empty()
        self.style.fontName = "Rep"
        self.style.fontSize = 9

        self.style.normal = style(
            getSampleStyleSheet()["Normal"],
            fontName="Rep",
            fontSize=self.style.fontSize,
            firstLineIndent=0,
        )
        self.style.heading1 = style(
            self.style.normal,
            fontName="Rep-Bold",
            fontSize=1.25 * self.style.fontSize,
            leading=1.25 * self.style.fontSize,
        )
        self.style.heading2 = style(
            self.style.normal,
            fontName="Rep-Bold",
            fontSize=1.15 * self.style.fontSize,
            leading=1.15 * self.style.fontSize,
        )
        self.style.heading3 = style(
            self.style.normal,
            fontName="Rep-Bold",
            fontSize=1.1 * self.style.fontSize,
            leading=1.2 * self.style.fontSize,
        )

        self.style.small = style(self.style.normal, fontSize=self.style.fontSize * 0.9)
        self.style.smaller = style(
            self.style.normal, fontSize=self.style.fontSize * 0.75
        )
        self.style.bold = style(self.style.normal, fontName="Rep-Bold")
        self.style.paragraph = style(self.style.normal, spaceBefore=1, spaceAfter=1)
        self.style.table = (
            ("FONT", (0, 0), (-1, -1), "Rep", self.style.fontSize),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("FIRSTLINEINDENT", (0, 0), (-1, -1), 0),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        )

        self.style.tableHeadLine = self.style.table + (
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("RIGHTPADDING", (0, 0), (0, -1), 2 * mm),
            ("LINEABOVE", (0, 0), (-1, 0), 0.2, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 0.2, colors.black),
            ("FONT", (0, 0), (-1, 0), "Rep-Bold", self.style.fontSize),
            ("TOPPADDING", (0, 0), (-1, 0), 1),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        )

        self.style.tableHead = self.style.tableHeadLine + (
            ("TOPPADDING", (0, 1), (-1, 1), 1),
        )

        self.bounds = Empty()
        self.bounds.N = 275 * mm
        self.bounds.E = 190 * mm
        self.bounds.S = 18 * mm
        self.bounds.W = 20 * mm
        self.bounds.outsideN = self.bounds.N + 5 * mm
        self.bounds.outsideS = self.bounds.S - 5 * mm
        self.style.tableColumns = (self.bounds.E - self.bounds.W - 20 * mm, 20 * mm)
        self.style.tableColumnsLeft = list(reversed(self.style.tableColumns))

    def init_letter(self, page_fn, page_fn_later=None, address_y=None, address_x=None):
        self.generate_style()

        frame_kwargs = {
            "showBoundary": self.show_boundaries,
            "leftPadding": 0,
            "rightPadding": 0,
            "topPadding": 0,
            "bottomPadding": 0,
        }

        address_frame = Frame(
            self.bounds.W,
            address_y or 20.2 * cm,
            self.bounds.E - self.bounds.W,
            40 * mm,
            **frame_kwargs
        )
        rest_frame = Frame(
            self.bounds.W,
            self.bounds.S,
            self.bounds.E - self.bounds.W,
            18.2 * cm,
            **frame_kwargs
        )
        full_frame = Frame(
            self.bounds.W,
            self.bounds.S,
            self.bounds.E - self.bounds.W,
            self.bounds.N - self.bounds.S,
            **frame_kwargs
        )

        self.doc.addPageTemplates(
            [
                PageTemplate(
                    id="First", frames=[address_frame, rest_frame], onPage=page_fn
                ),
                PageTemplate(
                    id="Later", frames=[full_frame], onPage=page_fn_later or page_fn
                ),
            ]
        )
        self.story.append(NextPageTemplate("Later"))

    def stationery(self):
        pdf = self

        def _fn(canvas, doc):
            canvas.saveState()

            canvas.setFont(pdf.style.fontName + "-Bold", 10)
            canvas.drawString(
                pdf.bounds.W, pdf.bounds.outsideN, settings.WORKBENCH.PDF_COMPANY
            )

            canvas.setFont(pdf.style.fontName, 6)
            canvas.drawString(
                pdf.bounds.W, pdf.bounds.outsideS, settings.WORKBENCH.PDF_ADDRESS
            )

            canvas.setFont(pdf.style.fontName, 6)
            canvas.drawRightString(
                pdf.bounds.E, pdf.bounds.outsideS, _("page %d") % doc.page
            )

            canvas.restoreState()

            pdf.draw_watermark(canvas)

        return _fn

    def init_offer(self):
        self.init_letter(page_fn=self.stationery())

    def init_invoice(self):
        self.init_letter(page_fn=self.stationery())

    def postal_address(self, postal_address):
        self.p(postal_address)
        self.next_frame()

    def table_services(self, services):
        if not services:
            return

        table = [(_("Services"), "")]
        for service in services:
            table.append(
                (
                    MarkupParagraph(
                        "<b>%s</b><br/>%s"
                        % (sanitize(service.title), sanitize(service.description)),
                        self.style.normal,
                    ),
                    service.service_cost.quantize(Z),
                )
            )

        self.table(table, self.style.tableColumns, self.style.tableHead)

    def table_total(self, instance):
        total = [(_("subtotal"), currency(instance.subtotal.quantize(Z)))]
        if instance.discount:
            total.append((_("discount"), currency(-instance.discount.quantize(Z))))
        if getattr(instance, "down_payment_total", None):
            for invoice in instance.down_payment_invoices.all():
                total.append(
                    (
                        "%s: %s (%s)"
                        % (
                            _("Down payment"),
                            invoice,
                            invoice.invoiced_on.strftime("%d.%m.%Y")
                            if invoice.invoiced_on
                            else _("NO DATE YET"),
                        ),
                        currency(-invoice.total_excl_tax.quantize(Z)),
                    )
                )
        if instance.tax_amount:
            total.append(
                (
                    "%0.1f%% %s" % (instance.tax_rate, _("tax")),
                    currency(instance.tax_amount.quantize(Z)),
                )
            )

        if len(total) > 1:
            self.table(total, self.style.tableColumns, self.style.tableHead)
            self.spacer(0.7 * mm)

        self.table(
            [(instance.total_title, currency(instance.total.quantize(Z)))],
            self.style.tableColumns,
            self.style.tableHeadLine,
        )

    def process_offer(self, offer):
        if offer.status not in {offer.OFFERED, offer.ACCEPTED}:
            self.watermark(str(offer.get_status_display()))

        self.postal_address(offer.postal_address)

        self.h1(offer.title)
        self.spacer(2 * mm)

        self.table(
            [
                (_("offer"), "%s/%s" % (offer.code, offer.owned_by.get_short_name())),
                (
                    _("date"),
                    (
                        local_date_format(offer.offered_on, "d.m.Y")
                        if offer.offered_on
                        else MarkupParagraph(
                            "<b>%s</b>" % _("NO DATE YET"), style=self.style.bold
                        )
                    ),
                ),
                (
                    _("valid until"),
                    (
                        local_date_format(
                            offer.offered_on + timedelta(days=60), "d.m.Y"
                        )
                        if offer.offered_on
                        else MarkupParagraph(
                            "<b>%s</b>" % _("NO DATE YET"), style=self.style.bold
                        )
                    ),
                ),
            ],
            self.style.tableColumnsLeft,
            self.style.table,
        )

        if offer.description:
            self.spacer(5 * mm)
            self.p(offer.description)

        self.spacer()
        self.table_services(offer.services.all())
        self.table_total(offer)

        self.spacer()
        self.p(settings.WORKBENCH.PDF_OFFER_TERMS)

    def process_invoice(self, invoice):
        if invoice.status not in {invoice.SENT, invoice.REMINDED, invoice.PAID}:
            self.watermark(str(invoice.get_status_display()))

        self.postal_address(invoice.postal_address)

        self.h1(invoice.title)
        self.spacer(2 * mm)

        self.table(
            [
                (
                    _("invoice"),
                    "%s/%s" % (invoice.code, invoice.owned_by.get_short_name()),
                ),
                (
                    _("date"),
                    (
                        local_date_format(invoice.invoiced_on, "d.m.Y")
                        if invoice.invoiced_on
                        else MarkupParagraph(
                            "<b>%s</b>" % _("NO DATE YET"), style=self.style.bold
                        )
                    ),
                ),
                ("MwSt.-Nr.", settings.WORKBENCH.PDF_VAT_NO),
            ],
            self.style.tableColumnsLeft,
            self.style.table,
        )

        if invoice.description:
            self.spacer(5 * mm)
            self.p(invoice.description)

        self.spacer()
        self.table_services(invoice.services.all())
        self.table_total(invoice)

        self.spacer()
        self.p(
            settings.WORKBENCH.PDF_INVOICE_PAYMENT
            % {
                "code": invoice.code,
                "due": (
                    local_date_format(invoice.due_on, "d.m.Y")
                    if invoice.due_on
                    else _("NO DATE YET")
                ),
            }
        )


pdf_response = partial(_pdf_response, pdfdocument=PDFDocument)
