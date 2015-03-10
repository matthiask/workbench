from copy import deepcopy
from decimal import Decimal as D
from functools import partial

from django.conf import settings
from django.template.defaultfilters import date as date_fmt
from django.utils.translation import ugettext as _

from pdfdocument.document import (
    MarkupParagraph, sanitize, PDFDocument as _PDFDocument, cm, mm, colors,
    getSampleStyleSheet, register_fonts_from_paths)
from pdfdocument.utils import pdf_response as _pdf_response


register_fonts_from_paths(
    font_name='Rep',
    **settings.FONTS)


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
        self.style.fontSize = 9

        self.style.normal = style(
            getSampleStyleSheet()['Normal'],
            fontName='Rep',
            fontSize=self.style.fontSize,
            firstLineIndent=0,
        )
        self.style.heading1 = style(
            self.style.normal,
            fontName='Rep-Bold',
            fontSize=1.5 * self.style.fontSize,
            leading=2 * self.style.fontSize,
        )
        self.style.heading2 = style(
            self.style.normal,
            fontName='Rep-Bold',
            fontSize=1.25 * self.style.fontSize,
            leading=1.75 * self.style.fontSize,
        )
        self.style.heading3 = style(
            self.style.normal,
            fontName='Rep-Bold',
            fontSize=1.1 * self.style.fontSize,
            leading=1.5 * self.style.fontSize,
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

    def offer_stationery(self):
        pdf = self

        def _fn(canvas, doc):
            canvas.saveState()

            canvas.setFont(pdf.style.fontName + '-Bold', 10)
            canvas.drawString(
                26 * mm,
                284 * mm,
                'FEINHEIT GmbH')

            canvas.setFont(pdf.style.fontName, 6)
            canvas.drawCentredString(
                108 * mm,
                11 * mm,
                'Bestandteil dieser Offerte sind die zum Zeitpunkt'
                ' des Vertragsabschlusses aktuellen Allgemeinen'
                ' Geschäftsbedingungen der FEINHEIT GmbH.')
            canvas.drawCentredString(
                108 * mm,
                8 * mm,
                'Die jeweils aktuelle Version'
                ' finden Sie auf www.feinheit.ch/agb/.')

            canvas.setFont(pdf.style.fontName, 6)
            canvas.drawRightString(
                190 * mm,
                8 * mm,
                '%d/%d' % doc.page_index())

            canvas.restoreState()

        return _fn

    def init_offer(self):
        super().init_letter(
            page_fn=self.offer_stationery(),
        )

    def postal_address(self, postal_address):
        self.smaller('FEINHEIT GmbH · Molkenstrasse 21 · 8004 Zürich')
        self.spacer(1 * mm)

        self.p(postal_address)
        self.next_frame()

    def date_line(self, date, short_name=None):
        elements = [
            date_fmt(date, 'l, d.m.Y'),
            short_name,
        ]
        self.smaller(' / '.join(e for e in elements))

    def table_stories(self, stories):
        table = [
            ('', _('Services')),
        ]
        for story in stories:
            table.append([
                sum(
                    (D(e) * D(p) for e, p in story['billing']),
                    Z,
                ).quantize(Z),
                MarkupParagraph('<b>%s</b><br/>%s' % (
                    sanitize(story['title']),
                    sanitize(story['description']),
                ), self.style.normal),
            ])

        self.table(
            table,
            (1.8 * cm, 14.6 * cm),
            self.style.tableHead)

    def table_total(self, instance):
        total = [
            (instance.subtotal.quantize(Z), _('subtotal')),
        ]
        if instance.discount:
            total.append((
                instance.discount.quantize(Z),
                _('discount'),
            ))
        if instance.tax_amount:
            total.append((
                instance.tax_amount.quantize(Z),
                '%0.1f%% %s' % (instance.tax_rate, _('tax')),
            ))

        if len(total) > 1:
            self.table(total, (1.8 * cm, 14.6 * cm), self.style.tableHead)

        self.table([
            (instance.total.quantize(Z), _('total incl. tax')),
        ], (1.8 * cm, 14.6 * cm), self.style.tableHeadLine)

    def process_offer(self, offer):
        self.postal_address(offer.postal_address)
        self.date_line(
            offer.offered_on,
            short_name=offer.owned_by.get_short_name())

        self.h1(offer.title)
        self.spacer(2 * mm)

        self.p(offer.description)
        self.spacer()

        if offer.story_data and offer.story_data.get('stories'):
            self.table_stories(offer.story_data['stories'])
        self.table_total(offer)


pdf_response = partial(_pdf_response, pdfdocument=PDFDocument)
