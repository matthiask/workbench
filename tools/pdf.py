from copy import deepcopy
from decimal import Decimal as D
from datetime import timedelta
from functools import partial

from django.conf import settings
from django.utils.translation import ugettext as _

from pdfdocument.document import (
    Frame, PageTemplate, NextPageTemplate,
    MarkupParagraph, sanitize, PDFDocument as _PDFDocument, cm, mm, colors,
    getSampleStyleSheet, register_fonts_from_paths)
from pdfdocument.utils import pdf_response as _pdf_response

from tools.formats import local_date_format
from workbench.templatetags.workbench import currency


register_fonts_from_paths(
    font_name='Rep',
    **settings.WORKBENCH.FONTS)


Z = D('0.00')


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
        self.style.fontName = 'Rep'
        self.style.fontSize = 10

        self.style.normal = style(
            getSampleStyleSheet()['Normal'],
            fontName='Rep',
            fontSize=self.style.fontSize,
            firstLineIndent=0,
        )
        self.style.heading1 = style(
            self.style.normal,
            fontName='Rep-Bold',
            fontSize=1.25 * self.style.fontSize,
            leading=1.25 * self.style.fontSize,
        )
        self.style.heading2 = style(
            self.style.normal,
            fontName='Rep-Bold',
            fontSize=1.15 * self.style.fontSize,
            leading=1.15 * self.style.fontSize,
        )
        self.style.heading3 = style(
            self.style.normal,
            fontName='Rep-Bold',
            fontSize=1.1 * self.style.fontSize,
            leading=1.2 * self.style.fontSize,
        )

        self.style.small = style(
            self.style.normal,
            fontSize=self.style.fontSize * 0.9,
        )
        self.style.smaller = style(
            self.style.normal,
            fontSize=self.style.fontSize * 0.75,
        )
        self.style.bold = style(
            self.style.normal,
            fontName='Rep-Bold',
        )
        self.style.paragraph = style(
            self.style.normal,
            spaceBefore=1,
            spaceAfter=1,
        )
        self.style.table = (
            ('FONT', (0, 0), (-1, -1), 'Rep', self.style.fontSize),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('FIRSTLINEINDENT', (0, 0), (-1, -1), 0),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        )

        self.style.tableHeadLine = self.style.table + (
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('RIGHTPADDING', (0, 0), (0, -1), 2 * mm),

            ('LINEABOVE', (0, 0), (-1, 0), 0.2, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 0.2, colors.black),
            ('FONT', (0, 0), (-1, 0), 'Rep-Bold', self.style.fontSize),
            ('TOPPADDING', (0, 0), (-1, 0), 1),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        )

        self.style.tableHead = self.style.tableHeadLine + (
            ('TOPPADDING', (0, 1), (-1, 1), 1),
        )

        self.bounds = Empty()
        self.bounds.N = 280 * mm
        self.bounds.E = 187 * mm
        self.bounds.S = 12 * mm
        self.bounds.W = 23 * mm
        self.style.tableColumns = (18 * mm, 146 * mm)

    def init_letter(self, page_fn, page_fn_later=None,
                    address_y=None, address_x=None):
        self.generate_style()

        frame_kwargs = {
            'showBoundary': self.show_boundaries,
            'leftPadding': 0,
            'rightPadding': 0,
            'topPadding': 0,
            'bottomPadding': 0,
        }

        address_frame = Frame(
            self.bounds.W,
            address_y or 20.2 * cm,
            16.4 * cm,
            4 * cm,
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

        self.doc.addPageTemplates([
            PageTemplate(
                id='First',
                frames=[address_frame, rest_frame],
                onPage=page_fn),
            PageTemplate(
                id='Later',
                frames=[full_frame],
                onPage=page_fn_later or page_fn),
        ])
        self.story.append(NextPageTemplate('Later'))

    def offer_stationery(self):
        pdf = self

        def _fn(canvas, doc):
            canvas.saveState()

            canvas.setFont(pdf.style.fontName + '-Bold', 10)
            canvas.drawString(
                pdf.bounds.W,
                pdf.bounds.N,
                settings.WORKBENCH.PDF_COMPANY)

            canvas.setFont(pdf.style.fontName, 6)
            for i, text in enumerate(reversed(
                    settings.WORKBENCH.PDF_OFFER_TERMS)):
                canvas.drawString(
                    pdf.bounds.W,
                    pdf.bounds.S + 3 * i * mm,
                    text)

            canvas.setFont(pdf.style.fontName, 6)
            canvas.drawRightString(
                pdf.bounds.E,
                pdf.bounds.S,
                _('page %d') % doc.page)

            canvas.restoreState()

        return _fn

    def invoice_stationery(self):
        pdf = self

        def _fn(canvas, doc):
            canvas.saveState()

            canvas.setFont(pdf.style.fontName + '-Bold', 10)
            canvas.drawString(
                pdf.bounds.W,
                pdf.bounds.N,
                settings.WORKBENCH.PDF_COMPANY)

            canvas.setFont(pdf.style.fontName, 6)
            canvas.drawString(
                pdf.bounds.W,
                pdf.bounds.S,
                settings.WORKBENCH.PDF_ADDRESS)

            canvas.setFont(pdf.style.fontName, 6)
            canvas.drawRightString(
                pdf.bounds.E,
                pdf.bounds.S,
                _('page %d') % doc.page)

            canvas.restoreState()

        return _fn

    def init_offer(self):
        super().init_letter(
            page_fn=self.offer_stationery(),
        )

    def init_invoice(self):
        super().init_letter(
            page_fn=self.invoice_stationery(),
        )

    def postal_address(self, postal_address):
        self.p(postal_address)
        self.next_frame()

    def date_line(self, date, *args):
        elements = [
            local_date_format(date, 'l, d.m.Y') if date else _('NO DATE YET')]
        elements.extend(args)
        self.smaller(' / '.join(e for e in elements))

    def table_services(self, services):
        if not services:
            return

        table = [
            ('', _('Services')),
        ]
        for service in services:
            table.append((
                '',
                MarkupParagraph('<b>%s</b><br/>%s' % (
                    sanitize(service.title),
                    sanitize(service.description),
                ), self.style.normal),
            ))
            for effort in service.efforts.all():
                table.append((
                    effort.cost.quantize(Z),
                    effort.service_type.title,
                ))
            for cost in service.costs.all():
                table.append((
                    cost.cost.quantize(Z),
                    cost.title,
                ))

        self.table(
            table,
            self.style.tableColumns,
            self.style.tableHead)

    def table_total(self, instance):
        total = [
            (currency(instance.subtotal.quantize(Z)), _('subtotal')),
        ]
        if instance.discount:
            total.append((
                currency(instance.discount.quantize(Z)),
                _('discount'),
            ))
        if instance.tax_amount:
            total.append((
                currency(instance.tax_amount.quantize(Z)),
                '%0.1f%% %s' % (instance.tax_rate, _('tax')),
            ))

        if len(total) > 1:
            self.table(total, self.style.tableColumns, self.style.tableHead)
            self.spacer(.7 * mm)

        self.table([
            (currency(instance.total.quantize(Z)), _('total CHF incl. tax')),
        ], self.style.tableColumns, self.style.tableHeadLine)

    def process_offer(self, offer):
        self.postal_address(offer.postal_address)
        self.date_line(
            offer.offered_on,
            offer.owned_by.get_short_name(),
            offer.code)

        self.h1(offer.title)
        self.spacer(2 * mm)

        self.p(offer.description)
        self.spacer()

        self.table_services(offer.services.prefetch_related(
            'efforts', 'costs'))
        self.table_total(offer)

    def process_invoice(self, invoice):
        self.postal_address(invoice.postal_address)

        self.h1(invoice.title)
        self.spacer(2 * mm)

        self.table([
            (_('invoice'), '%s/%s' % (
                invoice.code, invoice.owned_by.get_short_name())),
            (_('date'), (
                local_date_format(invoice.invoiced_on, 'd.m.Y')
                if invoice.invoiced_on
                else _('NO DATE YET')
            )),
            ('MwSt.-Nr.', settings.WORKBENCH.PDF_VAT_NO),
        ], self.style.tableColumns, self.style.table)

        if invoice.description:
            self.spacer(5 * mm)
            self.p(invoice.description)

        self.spacer()
        self.table_total(invoice)

        self.spacer()
        self.p(settings.WORKBENCH.PDF_INVOICE_PAYMENT % {
            'code': invoice.code,
            'days': 15,
            'due': local_date_format(
                invoice.invoiced_on + timedelta(days=15),
                'd.m.Y') if invoice.invoiced_on else _('NO DATE YET'),
        })


pdf_response = partial(_pdf_response, pdfdocument=PDFDocument)
