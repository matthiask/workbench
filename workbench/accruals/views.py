from decimal import Decimal

from django import http
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from workbench import generic
from workbench.accruals.models import Accrual
from workbench.tools.xlsx import XLSXDocument


class CutoffDateDetailView(generic.DetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get("create_accruals"):
            Accrual.objects.generate_accruals(cutoff_date=self.object.day)
            messages.success(request, _("Generated accruals."))
            return redirect(self.object)

        accruals = Accrual.objects.filter(cutoff_date=self.object.day).select_related(
            "invoice__project", "invoice__owned_by"
        )

        if request.GET.get("xlsx"):
            xlsx = XLSXDocument()
            xlsx.table_from_queryset(
                accruals,
                additional=[
                    (
                        _("accrual"),
                        lambda item: item.invoice.total_excl_tax
                        * (Decimal(100) - item.work_progress)
                        / 100,
                    )
                ],
            )
            return xlsx.to_response(
                "accruals-{}.xlsx".format(self.object.day.isoformat())
            )

        return self.render_to_response(self.get_context_data(accruals=accruals))

    def post(self, request, *args, **kwargs):
        accrual = Accrual.objects.get(pk=request.POST["id"])
        accrual.accrual = request.POST["accrual"]
        accrual.save()
        return http.HttpResponse(status=202)
