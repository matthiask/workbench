import datetime as dt

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _, ngettext

from workbench import generic
from workbench.credit_control.forms import AssignCreditEntriesForm, ExportDebtorsForm
from workbench.credit_control.reporting import paid_debtors_zip
from workbench.invoices.models import Invoice
from workbench.reporting.models import FreezeDate


class AccountStatementUploadView(generic.CreateView):
    def get_context_data(self, **kwargs):
        kwargs.setdefault("title", _("Upload account statement"))
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        entries = form.save()
        messages.success(
            self.request,
            ngettext(
                "Created %s credit entry.", "Created %s credit entries.", len(entries)
            )
            % len(entries),
        )
        return redirect("credit_control_creditentry_list")


class AssignCreditEntriesView(generic.CreateView):
    form_class = AssignCreditEntriesForm

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if not form.entries:
            messages.success(
                request, _("All credit entries have already been assigned.")
            )
            return redirect("credit_control_creditentry_list")
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            _("%(class)s have been updated successfully.")
            % {"class": self.model._meta.verbose_name_plural},
        )
        return redirect(".")

    def get_context_data(self, **kwargs):
        kwargs.setdefault("title", _("Assign credit entries"))
        return super().get_context_data(**kwargs)


def export_debtors(request):
    args = (request.POST,) if request.method == "POST" else ()
    form = ExportDebtorsForm(*args, request=request)

    if form.is_valid():
        data = form.cleaned_data
        response = HttpResponse(
            content_type="application/octet-stream",
            headers={
                "content-disposition": f'attachment; filename="debtors-{data["year"]}.zip"',
            },
        )

        date_range = [dt.date(data["year"], 1, 1), dt.date(data["year"], 12, 31)]
        paid_debtors_zip(date_range, file=response, qr=False)

        if archive := data.get("archive"):
            (
                Invoice.objects.filter(
                    invoiced_on__lte=archive, archived_at__isnull=True
                )
                .exclude(status=Invoice.IN_PREPARATION)
                .update(archived_at=timezone.now())
            )

            FreezeDate.objects.create(up_to=archive)

        return response

    return render(
        request,
        "credit_control/export_debtors.html",
        {"form": form, "title": _("Export debtors")},
    )
