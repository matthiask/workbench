import datetime as dt

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
            if self.object.day > dt.date.today():
                messages.warning(
                    request, _("Cannot generate accruals for future cutoff dates.")
                )
            else:
                Accrual.objects.generate_accruals(cutoff_date=self.object.day)
                messages.success(request, _("Generated accruals."))
            return redirect(self.object)

        accruals = Accrual.objects.filter(cutoff_date=self.object.day).select_related(
            "invoice__project", "invoice__owned_by"
        )

        if request.GET.get("xlsx"):
            xlsx = XLSXDocument()
            xlsx.table_from_queryset(
                accruals, additional=[(_("accrual"), lambda item: item.accrual)]
            )
            return xlsx.to_response(
                "accruals-{}.xlsx".format(self.object.day.isoformat())
            )

        return self.render_to_response(self.get_context_data(accruals=accruals))

    def post(self, request, *args, **kwargs):
        accrual = Accrual.objects.get(pk=request.POST["id"])
        accrual.work_progress = request.POST["work_progress"]
        accrual.save()
        return http.HttpResponse(status=202)
