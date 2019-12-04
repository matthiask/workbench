from django.utils.text import capfirst
from django.utils.translation import gettext as _

from workbench import generic
from workbench.expenses.models import ExpenseReport
from workbench.tools.formats import currency, local_date_format
from workbench.tools.pdf import MarkupParagraph, mm, pdf_response


class ExpenseReportPDFView(generic.DetailView):
    model = ExpenseReport

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(
            self.object.code,
            as_attachment=request.GET.get("disposition") == "attachment",
        )
        pdf.init_report()
        pdf.watermark("" if self.object.closed_on else _("In preparation"))

        pdf.h1(_("expense report"))
        pdf.spacer(2 * mm)
        pdf.table(
            [
                (_("responsible"), self.object.owned_by.get_full_name()),
                (_("created at"), local_date_format(self.object.created_at)),
                (_("status"), capfirst(self.object.pretty_status)),
            ],
            pdf.style.tableColumnsLeft,
            pdf.style.table,
        )
        pdf.spacer(5 * mm)

        pdf.table(
            [(_("receipt"), "", _("total"))]
            + [
                (
                    "%d." % (index + 1),
                    MarkupParagraph(
                        "%s<br />%s: %s<br />%s<br />&nbsp;"
                        % (
                            local_date_format(cost.rendered_on),
                            cost.service.project,
                            cost.service,
                            cost.description,
                        ),
                        pdf.style.normal,
                    ),
                    currency(cost.third_party_costs),
                )
                for index, cost in enumerate(
                    self.object.expenses.select_related(
                        "service__project__owned_by"
                    ).order_by("rendered_on", "pk")
                )
            ],
            (10 * mm, pdf.bounds.E - pdf.bounds.W - 10 * mm - 16 * mm, 16 * mm),
            pdf.style.tableHead,
        )

        pdf.spacer(0.7 * mm)
        pdf.table(
            [(_("total"), currency(self.object.total))],
            pdf.style.tableColumns,
            pdf.style.tableHeadLine,
        )

        pdf.generate()

        return response
