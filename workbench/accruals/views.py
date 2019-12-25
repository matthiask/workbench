import datetime as dt

from django import forms, http
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from workbench import generic
from workbench.accounts.models import User
from workbench.accruals.models import Accrual
from workbench.tools.forms import Form
from workbench.tools.xlsx import WorkbenchXLSXDocument


class AccrualFilterForm(Form):
    owned_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("owned_by") == -1:
            queryset = queryset.filter(invoice__project__owned_by=self.request.user)
        elif data.get("owned_by") == 0:
            queryset = queryset.filter(invoice__project__owned_by__is_active=False)
        elif data.get("owned_by"):
            queryset = queryset.filter(invoice__project__owned_by=data.get("owned_by"))
        return queryset


class CutoffDateDetailView(generic.DetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get("create_accruals"):
            if self.object.day > dt.date.today():
                messages.warning(
                    request, _("Cannot generate accruals for future cutoff dates.")
                )
            else:
                Accrual.objects.generate_accruals(
                    cutoff_date=self.object.day, save=True
                )
                messages.success(request, _("Generated accruals."))
            return redirect(self.object)

        accruals = Accrual.objects.filter(cutoff_date=self.object.day).select_related(
            "invoice__project", "invoice__owned_by"
        )
        filter_form = AccrualFilterForm(request.GET, request=request)
        if not filter_form.is_valid():
            return http.HttpResponseRedirect(".")
        accruals = filter_form.filter(accruals)

        if request.GET.get("xlsx"):
            xlsx = WorkbenchXLSXDocument()
            xlsx.accruals(accruals)
            return xlsx.to_response(
                "accruals-{}.xlsx".format(self.object.day.isoformat())
            )

        return self.render_to_response(
            self.get_context_data(accruals=accruals, form=filter_form)
        )

    def post(self, request, *args, **kwargs):
        accrual = Accrual.objects.get(pk=request.POST["id"])
        accrual.work_progress = request.POST["work_progress"]
        accrual.save()
        return http.HttpResponse(status=202)
