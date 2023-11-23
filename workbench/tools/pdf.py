import datetime as dt
from copy import deepcopy
from decimal import Decimal as D

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

from workbench.invoices.models import Invoice
from workbench.tools.formats import Z2, currency, hours, local_date_format
from workbench.tools.models import CalculationModel


register_fonts_from_paths(font_name="Rep", **settings.WORKBENCH.FONTS)


Z = D("0.00")


class Empty:
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
        self.style.tableServices = (
            *self.style.table,
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        )

        self.style.tableHeadLine = (
            *self.style.table,
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("RIGHTPADDING", (0, 0), (0, -1), 2 * mm),
            ("LINEABOVE", (0, 0), (-1, 0), 0.2, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 0.2, colors.black),
            ("FONT", (0, 0), (-1, 0), "Rep-Bold", self.style.fontSize),
            ("TOPPADDING", (0, 0), (-1, 0), 1),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        )

        self.style.tableHead = (
            *self.style.tableHeadLine,
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
            **frame_kwargs,
        )
        self.rest_frame = Frame(
            self.bounds.W,
            self.bounds.S,
            self.bounds.E - self.bounds.W,
            18.2 * cm,
            **frame_kwargs,
        )
        self.full_frame = Frame(
            self.bounds.W,
            self.bounds.S,
            self.bounds.E - self.bounds.W,
            self.bounds.N - self.bounds.S,
            **frame_kwargs,
        )
        self.bill_frame = Frame(
            0,
            0,
            21 * cm,
            10.6 * cm,
            showBoundary=False,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
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

    def init_invoice_letter(self, *, page_fn=None, page_fn_later=None):
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
                    id="QR",
                    frames=[self.bill_frame],
                    onPage=page_fn,
                ),
                PageTemplate(
                    id="Later",
                    frames=[self.full_frame],
                    onPage=page_fn_later or page_fn,
                ),
            ]
        )

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
        self.table(
            [
                (
                    MarkupParagraph(
                        "<b>{}</b> {}".format(
                            sanitize(service.title),
                            _("(optional)") if is_optional else "",
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
            ],
            self.style.tableThreeColumns,
            self.style.tableServices,
        )

        if stripped := service.description.strip():
            self.p(stripped)
        self.spacer(1 * mm)

    def services_row_with_details(self, service):
        is_optional = getattr(service, "is_optional", False)

        self.table(
            [
                (
                    MarkupParagraph(
                        "<b>{}</b> {}".format(
                            sanitize(service.title),
                            _("(optional)") if is_optional else "",
                        ),
                        self.style.normal,
                    ),
                    "",
                    "",
                ),
            ],
            self.style.tableThreeColumns,
            self.style.tableServices,
        )
        if stripped := service.description.strip():
            self.p(stripped)
            self.spacer(0.25 * mm)
        self.table(
            [
                (
                    MarkupParagraph(
                        ", ".join(
                            filter(
                                None,
                                [
                                    (
                                        "{} {} à {}/h".format(
                                            hours(service.effort_hours),
                                            service.effort_type,
                                            currency(service.effort_rate),
                                        )
                                    )
                                    if service.effort_hours and service.effort_rate
                                    else "",
                                    (
                                        "{} {}".format(
                                            currency(service.cost), _("fixed costs")
                                        )
                                    )
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
            ],
            self.style.tableThreeColumns,
            self.style.tableServices,
        )
        self.spacer(1 * mm)

    def table_services(self, services, *, show_details=False):
        if not services:
            return

        fn = self.services_row_with_details if show_details else self.services_row
        self.table(
            [(_("Services"), "", "")],
            self.style.tableThreeColumns,
            self.style.tableHead,
        )
        self.spacer(2 * mm)

        for service in services:
            fn(service)
            # + list(chain.from_iterable(fn(service) for service in services)),

    def table_total(self, instance, *, optional_total=None):
        transform = lambda x: x  # noqa
        if getattr(instance, "type", None) == Invoice.CREDIT:
            transform = lambda x: -x  # noqa

        total = [(_("subtotal"), currency(transform(instance.subtotal).quantize(Z)))]
        if instance.discount:
            total.append(
                (_("discount"), currency(-transform(instance.discount).quantize(Z)))
            )
        if getattr(instance, "down_payment_total", None):
            for invoice in instance.down_payment_invoices.all():
                total.append(
                    (
                        MarkupParagraph(
                            "{}: {} ({})".format(
                                _("Down payment"),
                                Truncator(invoice).chars(60),
                                invoice.invoiced_on.strftime("%d.%m.%Y")
                                if invoice.invoiced_on
                                else _("NO DATE YET"),
                            ),
                            self.style.normal,
                        ),
                        currency(-transform(invoice.total_excl_tax).quantize(Z)),
                    )
                )
        if instance.liable_to_vat:
            total.append(
                (
                    "{:0.1f}% {}".format(instance.tax_rate, _("tax")),
                    currency(transform(instance.tax_amount).quantize(Z)),
                )
            )

        if len(total) > 1:
            self.table(total, self.style.tableColumns, self.style.tableHead)
            self.spacer(0.3 * mm)

        self.table(
            [(instance.total_title, currency(transform(instance.total).quantize(Z)))],
            self.style.tableColumns,
            self.style.tableHeadLine,
        )

        if optional_total:
            self.spacer(1 * mm)
            self.table(
                [
                    (
                        instance.optional_total_title,
                        MarkupParagraph(
                            "<i>%s</i>" % currency(optional_total), self.style.right
                        ),
                        "",
                    )
                ],
                self.style.tableThreeColumns,
                self.style.table,
            )

    def process_offer(self, offer):
        self.watermark(
            ""
            if offer.status in {offer.OFFERED, offer.ACCEPTED}
            else str(offer.get_status_display())
        )
        self.postal_address(offer.postal_address)
        self.h1(offer.title)
        self.spacer(2 * mm)
        self.table(
            [
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
            self.style.tableColumnsLeft,
            self.style.table,
        )
        if offer.description:
            self.spacer(5 * mm)
            self.p(offer.description)
        self.spacer(2 * mm)
        services = offer.services.all()
        self.table_services(
            services,
            show_details=offer.show_service_details,
        )
        self.table_total(
            offer,
            optional_total=sum(
                (service.service_cost for service in services if service.is_optional),
                Z2,
            ),
        )
        self.spacer(2 * mm)
        self.p(settings.WORKBENCH.PDF_OFFER_TERMS)

    def process_invoice(self, invoice):
        title = _("invoice")
        if invoice.type == invoice.DOWN_PAYMENT:
            title = _("down payment invoice")
        elif invoice.type == invoice.CREDIT:
            title = _("credit")

        self.watermark(
            ""
            if invoice.status in {invoice.SENT, invoice.PAID}
            else str(invoice.get_status_display())
        )
        self.postal_address(invoice.postal_address)
        self.h1(invoice.title)
        self.spacer(2 * mm)
        self.table(
            [
                (
                    title,
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
            self.style.tableColumnsLeft,
            self.style.table,
        )
        if invoice.description:
            self.spacer(5 * mm)
            self.p(invoice.description)
        self.spacer(2 * mm)
        if invoice.service_period:
            self.p("{}: {}".format(_("Service period"), invoice.service_period))
            self.spacer()
        self.table_services(
            invoice.services.all(),
            show_details=invoice.show_service_details,
        )
        self.table_total(invoice)
        self.spacer(2 * mm)
        self.p(
            (
                settings.WORKBENCH.PDF_CREDIT
                if invoice.type == invoice.CREDIT
                else settings.WORKBENCH.PDF_INVOICE_PAYMENT
            )
            % {
                "code": invoice.code,
                "due": (
                    local_date_format(invoice.due_on)
                    if invoice.due_on
                    else _("NO DATE YET")
                ),
            },
        )

        if getattr(settings.WORKBENCH, "QRBILL", None) and invoice.total > 0:
            self.story.append(NextPageTemplate("QR"))
            self.next_frame()
            self.append_qr_bill(invoice)
        else:
            self.story.append(NextPageTemplate("Later"))
            self.next_frame()

    def append_qr_bill(self, invoice):
        import tempfile

        from qrbill.bill import CombinedAddress, QRBill
        from svglib.svglib import svg2rlg

        bill = QRBill(
            amount=str(invoice.total),
            additional_information="{}: {}".format(
                capfirst(_("invoice")), invoice.code
            ),
            language=settings.WORKBENCH.PDF_LANGUAGE,
            **settings.WORKBENCH.QRBILL,
        )

        bill.debtor = CombinedAddress(**get_debtor_address(invoice.postal_address))

        with tempfile.NamedTemporaryFile(mode="w") as f:
            bill.as_svg(f)
            f.seek(0)
            drawing = svg2rlg(f.name)
            self.story.append(drawing)

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
            (*self.style.tableHead, ("ALIGN", (1, 0), (1, -1), "LEFT")),
        )

        total = CalculationModel(
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

    def table_columns(self, columns):
        given = sum(filter(None, columns))
        calculated = (self.bounds.E - self.bounds.W - given) / columns.count(None)
        return [calculated if col is None else col for col in columns]


def pdf_response(*args, **kwargs):
    activate(settings.WORKBENCH.PDF_LANGUAGE)
    kwargs["pdfdocument"] = PDFDocument
    return _pdf_response(*args, **kwargs)


def get_debtor_address(postal_address):
    address_lines = postal_address.splitlines()
    country = "CH"
    if address_lines and address_lines[-1] == "Liechtenstein":
        address_lines = address_lines[:-1]
        country = "LI"
    elif address_lines and "LI" in address_lines[-1]:
        country = "LI"

    if len(address_lines) < 3:
        name, line1, line2, *rest = [*address_lines, "", "", ""]
    elif len(address_lines) <= 4:
        name = " ".join(address_lines[0:-2])
        line1 = address_lines[-2]
        line2 = address_lines[-1]
    else:
        name = " ".join(address_lines[0:2])
        line1 = " ".join(address_lines[2:-1])
        line2 = address_lines[-1]

    return {
        "name": name[:70],
        "line1": line1[:70],
        "line2": line2[:70],
        "country": country,
    }
