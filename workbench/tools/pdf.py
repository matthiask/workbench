import datetime as dt
from copy import deepcopy
from decimal import Decimal as D
from itertools import chain

from django.conf import settings
from django.utils.text import Truncator, capfirst
from django.utils.translation import activate, gettext as _

from pdfdocument.document import (
    TA_RIGHT,
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

from workbench.tools.formats import currency, hours, local_date_format
from workbench.tools.models import ModelWithTotal


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
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("font_name", "Rep")
        kwargs.setdefault("font_size", 8.5)
        super().__init__(*args, **kwargs)

    def generate_style(self, *args, **kwargs):
        self.style = Empty()
        self.style.fontName = self.font_name
        self.style.fontSize = self.font_size

        self.style.normal = style(
            getSampleStyleSheet()["Normal"],
            fontName="Rep",
            fontSize=self.style.fontSize,
            firstLineIndent=0,
        )
        self.style.normalWithExtraLeading = style(
            self.style.normal,
            leading=1.75 * self.style.fontSize,
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

        self.style.right = style(self.style.normal, alignment=TA_RIGHT)

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
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
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
        self.style.tableColumns = (self.bounds.E - self.bounds.W - 32 * mm, 32 * mm)
        self.style.tableColumnsLeft = list(reversed(self.style.tableColumns))
        self.style.tableThreeColumns = (
            self.bounds.E - self.bounds.W - 32 * mm,
            16 * mm,
            16 * mm,
        )

        frame_kwargs = {
            "showBoundary": self.show_boundaries,
            "leftPadding": 0,
            "rightPadding": 0,
            "topPadding": 0,
            "bottomPadding": 0,
        }

        self.address_frame = Frame(
            self.bounds.W,
            20.2 * cm,
            self.bounds.E - self.bounds.W,
            40 * mm,
            **frame_kwargs
        )
        self.rest_frame = Frame(
            self.bounds.W,
            self.bounds.S,
            self.bounds.E - self.bounds.W,
            18.2 * cm,
            **frame_kwargs
        )
        self.full_frame = Frame(
            self.bounds.W,
            self.bounds.S,
            self.bounds.E - self.bounds.W,
            self.bounds.N - self.bounds.S,
            **frame_kwargs
        )

    def init_letter(self, *, page_fn=None, page_fn_later=None):
        page_fn = page_fn or self.stationery()
        self.generate_style()
        self.doc.addPageTemplates(
            [
                PageTemplate(
                    id="First",
                    frames=[self.address_frame, self.rest_frame],
                    onPage=page_fn,
                ),
                PageTemplate(
                    id="Later",
                    frames=[self.full_frame],
                    onPage=page_fn_later or page_fn,
                ),
            ]
        )
        self.story.append(NextPageTemplate("Later"))

    def init_report(self, *, page_fn=None):
        page_fn = page_fn or self.stationery()
        self.generate_style()
        self.doc.addPageTemplates(
            [PageTemplate(id="Page", frames=[self.full_frame], onPage=page_fn)]
        )

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
                pdf.bounds.E,
                pdf.bounds.outsideS,
                _("Page %d")
                % (
                    doc.page - doc.restartDocPageNumbers[doc.restartDocIndex - 1]
                    if doc.restartDocIndex
                    else doc.page
                ),
            )

            canvas.restoreState()

            pdf.draw_watermark(canvas)

        return _fn

    def postal_address(self, postal_address):
        self.p(postal_address)
        self.next_frame()

    def services_row(self, service):
        is_optional = getattr(service, "is_optional", False)
        return [
            (
                MarkupParagraph(
                    "<b>%s</b> %s<br/>%s"
                    % (
                        sanitize(service.title),
                        _("(optional)") if is_optional else "",
                        sanitize(service.description),
                    ),
                    self.style.normal,
                ),
                MarkupParagraph(
                    "<i>%s</i>" % currency(service.service_cost.quantize(Z)),
                    self.style.right,
                )
                if is_optional
                else "",
                "" if is_optional else currency(service.service_cost.quantize(Z)),
            )
        ]

    def services_row_with_details(self, service):
        is_optional = getattr(service, "is_optional", False)
        return [
            (
                MarkupParagraph(
                    "<b>%s</b> %s<br/>%s"
                    % (
                        sanitize(service.title),
                        _("(optional)") if is_optional else "",
                        sanitize(service.description),
                    ),
                    self.style.normal,
                ),
                "",
                "",
            ),
            (
                MarkupParagraph(
                    ", ".join(
                        filter(
                            None,
                            [
                                (
                                    "%s %s à %s/h"
                                    % (
                                        hours(service.effort_hours),
                                        service.effort_type,
                                        currency(service.effort_rate),
                                    )
                                )
                                if service.effort_hours and service.effort_rate
                                else "",
                                ("%s %s" % (currency(service.cost), _("fixed costs")))
                                if service.cost
                                else "",
                            ],
                        )
                    ),
                    self.style.normalWithExtraLeading,
                ),
                MarkupParagraph(
                    "<i>%s</i>" % currency(service.service_cost.quantize(Z)),
                    self.style.right,
                )
                if is_optional
                else "",
                "" if is_optional else currency(service.service_cost.quantize(Z)),
            ),
        ]

    def table_services(self, services, *, show_details=False):
        if not services:
            return

        fn = self.services_row_with_details if show_details else self.services_row
        self.table(
            [(_("Services"), "", "")]
            + list(chain.from_iterable(fn(service) for service in services)),
            self.style.tableThreeColumns,
            self.style.tableHead,
        )

    def table_total(self, instance):
        total = [(_("subtotal"), currency(instance.subtotal.quantize(Z)))]
        if instance.discount:
            total.append((_("discount"), currency(-instance.discount.quantize(Z))))
        if getattr(instance, "down_payment_total", None):
            for invoice in instance.down_payment_invoices.all():
                total.append(
                    (
                        MarkupParagraph(
                            "%s: %s (%s)"
                            % (
                                _("Down payment"),
                                Truncator(invoice).chars(60),
                                invoice.invoiced_on.strftime("%d.%m.%Y")
                                if invoice.invoiced_on
                                else _("NO DATE YET"),
                            ),
                            self.style.normal,
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

    def process_services_letter(self, instance, *, watermark, details, footer):
        self.watermark(watermark)
        self.postal_address(instance.postal_address)
        self.h1(instance.title)
        self.spacer(2 * mm)
        self.table(details, self.style.tableColumnsLeft, self.style.table)
        if instance.description:
            self.spacer(5 * mm)
            self.p(instance.description)
        self.spacer(2 * mm)
        if getattr(instance, "service_period", None):
            self.p("%s: %s" % (_("Service period"), instance.service_period))
            self.spacer()
        self.table_services(
            instance.services.all(),
            show_details=getattr(instance, "show_service_details", False),
        )
        self.table_total(instance)
        self.spacer(2 * mm)
        self.p(footer)

    def process_offer(self, offer):
        self.process_services_letter(
            offer,
            watermark=""
            if offer.status in {offer.OFFERED, offer.ACCEPTED}
            else str(offer.get_status_display()),
            details=[
                (_("offer"), offer.code),
                (
                    _("date"),
                    (
                        local_date_format(offer.offered_on)
                        if offer.offered_on
                        else MarkupParagraph(
                            "<b>%s</b>" % _("NO DATE YET"), style=self.style.bold
                        )
                    ),
                ),
                (_("Our reference"), offer.owned_by.get_full_name()),
                (
                    capfirst(_("valid until")),
                    (
                        local_date_format(offer.valid_until)
                        if offer.valid_until
                        else MarkupParagraph(
                            "<b>%s</b>" % _("NO DATE YET"), style=self.style.bold
                        )
                    ),
                ),
            ],
            footer=settings.WORKBENCH.PDF_OFFER_TERMS,
        )

    def process_invoice(self, invoice):
        self.process_services_letter(
            invoice,
            watermark=""
            if invoice.status in {invoice.SENT, invoice.PAID}
            else str(invoice.get_status_display()),
            details=[
                (
                    _("down payment invoice")
                    if invoice.type == invoice.DOWN_PAYMENT
                    else _("invoice"),
                    invoice.code,
                ),
                (
                    _("date"),
                    (
                        local_date_format(invoice.invoiced_on)
                        if invoice.invoiced_on
                        else MarkupParagraph(
                            "<b>%s</b>" % _("NO DATE YET"), style=self.style.bold
                        )
                    ),
                ),
                (_("Our reference"), invoice.owned_by.get_full_name()),
                ("MwSt.-Nr.", settings.WORKBENCH.PDF_VAT_NO),
            ],
            footer=settings.WORKBENCH.PDF_INVOICE_PAYMENT
            % {
                "code": invoice.code,
                "due": (
                    local_date_format(invoice.due_on)
                    if invoice.due_on
                    else _("NO DATE YET")
                ),
            },
        )

    def offers_pdf(self, *, project, offers):
        self.init_letter()
        self.p(offers[-1].postal_address)
        self.next_frame()
        self.p("Zürich, %s" % local_date_format(dt.date.today()))
        self.spacer()
        self.h1(project.title)
        if project.description:
            self.spacer(2 * mm)
            self.p(project.description)
        self.spacer()
        self.table(
            [
                tuple(
                    capfirst(title)
                    for title in (_("offer"), _("offered on"), _("total"))
                )
            ]
            + [
                (
                    MarkupParagraph(offer.title, self.style.normal),
                    local_date_format(offer.offered_on)
                    if offer.offered_on
                    else MarkupParagraph(
                        "<b>%s</b>" % _("NO DATE YET"), style=self.style.bold
                    ),
                    currency(offer.total_excl_tax),
                )
                for offer in offers
            ],
            (self.bounds.E - self.bounds.W - 40 * mm, 24 * mm, 16 * mm),
            self.style.tableHead + (("ALIGN", (1, 0), (1, -1), "LEFT"),),
        )

        total = ModelWithTotal(
            subtotal=sum((offer.total_excl_tax for offer in offers), Z),
            discount=Z,
            liable_to_vat=offers[0].liable_to_vat,
            tax_rate=offers[0].tax_rate,
        )
        total._calculate_total()
        total.total_title = offers[0].total_title
        self.table_total(total)

        self.restart()
        for offer in offers:
            self.init_letter()
            self.process_offer(offer)
            self.restart()

        self.generate()

    def dunning_letter(self, *, invoices):
        self.init_letter()
        self.p(invoices[-1].postal_address)
        self.next_frame()
        self.p("Zürich, %s" % local_date_format(dt.date.today()))
        self.spacer()
        self.h1("Zahlungserinnerung")
        self.spacer()
        self.mini_html(
            (
                """\
<p>Sehr geehrte Damen und Herren</p>
<p>Bei der beiliegenden Rechnung konnten wir leider noch keinen Zahlungseingang
verzeichnen. Wir bitten Sie, den ausstehenden Betrag innerhalb von 10 Tagen auf
das angegebene Konto zu überweisen. Bei allfälligen Unstimmigkeiten setzen Sie
sich bitte mit uns in Verbindung.</p>
<p>Falls sich Ihre Zahlung mit diesem Schreiben kreuzt, bitten wir Sie, dieses
als gegenstandslos zu betrachten.</p>
<p>Freundliche Grüsse</p>
<p>%s</p>"""
                if len(invoices) == 1
                else """\
<p>Sehr geehrte Damen und Herren</p>
<p>Bei den beiliegenden Rechnungen konnten wir leider noch keinen Zahlungseingang
verzeichnen. Wir bitten Sie, die ausstehenden Beträge innerhalb von 10 Tagen auf
das angegebene Konto zu überweisen. Bei allfälligen Unstimmigkeiten setzen Sie
sich bitte mit uns in Verbindung.</p>
<p>Falls sich Ihre Zahlung mit diesem Schreiben kreuzt, bitten wir Sie, dieses
als gegenstandslos zu betrachten.</p>
<p>Freundliche Grüsse</p>
<p>%s</p>"""
            )
            % settings.WORKBENCH.PDF_COMPANY
        )
        self.spacer()
        self.table(
            [tuple(capfirst(title) for title in (_("invoice"), _("date"), _("total")))]
            + [
                (
                    MarkupParagraph(invoice.title, self.style.normal),
                    local_date_format(invoice.invoiced_on),
                    currency(invoice.total),
                )
                for invoice in invoices
            ],
            (self.bounds.E - self.bounds.W - 40 * mm, 24 * mm, 16 * mm),
            self.style.tableHead + (("ALIGN", (1, 0), (1, -1), "LEFT"),),
        )
        self.restart()
        for invoice in invoices:
            self.init_letter(page_fn=self.stationery())
            self.process_invoice(invoice)
            self.restart()

    def table_columns(self, columns):
        given = sum(filter(None, columns))
        calculated = (self.bounds.E - self.bounds.W - given) / columns.count(None)
        return [calculated if col is None else col for col in columns]


def pdf_response(*args, **kwargs):
    activate(settings.WORKBENCH.PDF_LANGUAGE)
    kwargs["pdfdocument"] = PDFDocument
    return _pdf_response(*args, **kwargs)
