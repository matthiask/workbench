from datetime import date

import vanilla

from .invoicing_statistics import monthly_invoicing


class MonthlyInvoicingView(vanilla.TemplateView):
    template_name = "reporting/monthly_invoicing.html"

    def get_context_data(self, **kwargs):
        self.year = int(self.request.GET.get("year", date.today().year))  # XXX error
        return super().get_context_data(
            monthly_invoicing=monthly_invoicing(self.year), **kwargs
        )
