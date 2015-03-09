from decimal import Decimal as D
from functools import partial

from django.utils.translation import ugettext as _

from pdfdocument.document import Paragraph, PDFDocument as _PDFDocument, cm, mm
from pdfdocument.utils import pdf_response as _pdf_response


Z = D('0')


class PDFDocument(_PDFDocument):
    def offer_stationery(self):
        pdf = self

        def _fn(canvas, doc):
            canvas.saveState()

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

    def generate_style(self, *args, **kwargs):
        super().generate_style(*args, **kwargs)

        self.style.table_stories = [
            (1.7 * cm, 14.7 * cm),
            self.style.tableHead + (
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('RIGHTPADDING', (0, 0), (0, -1), 2 * mm),
            ),
        ]

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
                Paragraph(story['title'], self.style.bold),
            ])

            if story['description']:
                table.append([
                    '',
                    Paragraph(story['description'], self.style.normal),
                ])

        self.table(table, *self.style.table_stories)

    def table_total(self, instance):
        total = [
            (instance.subtotal.quantize(Z), _('subtotal')),
        ]
        if instance.discount:
            total.append([
                (instance.discount.quantize(Z), _('discount')),
            ])
        if instance.tax_amount:
            total.append([
                (instance.tax_amount.quantize(Z), _('tax amount')),
            ])

        if len(total) > 1:
            total.append([
                (instance.total.quantize(Z), _('total')),
            ])
        else:
            total = [
                (instance.total.quantize(Z), _('total')),
            ]

        self.table(total, *self.style.table_stories)


pdf_response = partial(_pdf_response, pdfdocument=PDFDocument)
