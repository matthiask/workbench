from datetime import date

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from workbench.invoices.models import Invoice
from workbench.reporting import invoicing_statistics, project_statistics
from workbench.tools.formats import local_date_format
from workbench.tools.models import Z
from workbench.tools.xlsx import WorkbenchXLSXDocument


def monthly_invoicing(request):
    year = None
    if "year" in request.GET:
        try:
            year = int(request.GET["year"])
        except Exception:
            return redirect(".")
    if not year:
        year = date.today().year

    return render(
        request,
        "reporting/monthly_invoicing.html",
        {
            "year": year,
            "monthly_invoicing": invoicing_statistics.monthly_invoicing(year),
        },
    )


def overdrawn_projects(request):
    return render(
        request,
        "reporting/overdrawn_projects.html",
        {"overdrawn_projects": project_statistics.overdrawn_projects()},
    )


class OpenItemsForm(forms.Form):
    cutoff_date = forms.DateField(
        label=_("cutoff date"),
        required=False,
        widget=forms.TextInput(attrs={"class": "datepicker"}),
    )

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault("cutoff_date", local_date_format(date.today()))
        super().__init__(data, *args, **kwargs)

    def open_items_list(self):
        open_items = (
            Invoice.objects.filter(
                ~Q(status__in=[Invoice.IN_PREPARATION, Invoice.REPLACED]),
                Q(invoiced_on__lt=self.cleaned_data["cutoff_date"]),
                Q(closed_on__gte=self.cleaned_data["cutoff_date"])
                | Q(closed_on__isnull=True),
            )
            .order_by("invoiced_on")
            .select_related("owned_by", "project")
        )

        return {
            "list": open_items,
            "total_excl_tax": sum((i.total_excl_tax for i in open_items), Z),
            "total": sum((i.total for i in open_items), Z),
        }


def open_items_list(request):
    form = OpenItemsForm(request.GET)
    if not form.is_valid():
        messages.warning(request, _("Form was invalid."))
        return redirect(".")

    if request.GET.get("xlsx"):
        xlsx = WorkbenchXLSXDocument()
        xlsx.table_from_queryset(
            form.open_items_list()["list"].select_related(
                "customer", "contact__organization", "owned_by", "project__owned_by"
            )
        )
        return xlsx.to_response(
            "open-items-list-{}.xlsx".format(
                form.cleaned_data["cutoff_date"].isoformat()
            )
        )

    return render(
        request,
        "reporting/open_items_list.html",
        {"form": form, "open_items_list": form.open_items_list()},
    )
