import csv
import io
from datetime import datetime
from decimal import Decimal

from django import forms
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.credit_control.models import CreditEntry
from workbench.invoices.models import Invoice
from workbench.templatetags.workbench import currency
from workbench.tools.formats import local_date_format
from workbench.tools.forms import ModelForm, Picker, Textarea
from workbench.tools.xlsx import WorkbenchXLSXDocument


class CreditEntrySearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(
            ("", _("All states")),
            ("pending", _("Pending")),
            ("processed", _("Processed")),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s") == "pending":
            queryset = queryset.filter(invoice__isnull=True, notes="")
        elif data.get("s") == "processed":
            queryset = queryset.filter(invoice__isnull=False).exclude(notes="")
        return queryset.select_related("invoice__project", "invoice__owned_by")

    def response(self, request, queryset):
        if request.GET.get("xlsx"):
            xlsx = WorkbenchXLSXDocument()
            xlsx.table_from_queryset(queryset)
            return xlsx.to_response("credit-entries.xlsx")


class CreditEntryForm(ModelForm):
    class Meta:
        model = CreditEntry
        fields = [
            "reference_number",
            "value_date",
            "total",
            "payment_notice",
            "invoice",
            "notes",
        ]
        widgets = {"invoice": Picker(model=Invoice), "notes": Textarea}


class AccountStatementUploadForm(forms.Form):
    statement = forms.FileField(label=_("account statement"))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    def save(self):
        f = io.StringIO()
        f.write(
            force_text(
                self.cleaned_data["statement"].read(), encoding="utf-8", errors="ignore"
            )
        )
        f.seek(0)
        dialect = csv.Sniffer().sniff(f.read(4096))
        f.seek(0)
        reader = csv.reader(f, dialect)
        next(reader)  # Skip first line
        entries = []
        while True:
            try:
                row = next(reader)
            except StopIteration:
                break
            if not row:
                continue
            try:
                day = datetime.strptime(row[8], "%d.%m.%Y").date()
                amount = row[7] and Decimal(row[7])
                reference = row[4]
            except (AttributeError, IndexError, ValueError):
                continue
            if day and amount:
                details = next(reader)
                entries.append(
                    [
                        reference,
                        {
                            "value_date": day,
                            "total": amount,
                            "payment_notice": "; ".join(
                                filter(None, (details[1], details[10], row[4]))
                            ),
                        },
                    ]
                )

        for reference, defaults in entries:
            CreditEntry.objects.get_or_create(
                reference_number=reference, defaults=defaults
            )

        return CreditEntry()


class AssignCreditEntriesForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")

        super().__init__(*args, **kwargs)

        self.entries = []
        for entry in CreditEntry.objects.filter(invoice__isnull=True, notes="")[:20]:
            self.fields["entry_{}_invoice".format(entry.pk)] = forms.TypedChoiceField(
                label=format_html(
                    "{}, {}", entry.total, local_date_format(entry.value_date, "d.m.Y")
                ),
                help_text=entry.payment_notice,
                choices=[(None, "----------")]
                + [
                    (
                        invoice.id,
                        format_html(
                            "<strong>{}, {}, {}</strong>"
                            if invoice.code in entry.payment_notice
                            else "{}, {}, {}",
                            invoice,
                            invoice.pretty_status(),
                            currency(invoice.total),
                        ),
                    )
                    for invoice in Invoice.objects.filter(
                        total=entry.total
                    ).select_related("owned_by", "project")[:100]
                ],
                coerce=int,
                required=False,
                widget=forms.RadioSelect,
            )

            self.fields["entry_{}_notes".format(entry.pk)] = forms.CharField(
                widget=Textarea({"rows": 1}), label=_("notes"), required=False
            )

            self.entries.append(
                (
                    entry,
                    "entry_{}_invoice".format(entry.pk),
                    "entry_{}_notes".format(entry.pk),
                )
            )

    def save(self):
        for entry, invoice_field, notes_field in self.entries:
            entry.invoice_id = self.cleaned_data.get(invoice_field) or None
            entry.notes = self.cleaned_data.get(notes_field, "")
            entry.save()

            if entry.invoice and entry.invoice.status != entry.invoice.PAID:
                entry.invoice.status = entry.invoice.PAID
                entry.invoice.closed_on = entry.value_date
                entry.invoice.payment_notice = entry.payment_notice
                entry.invoice.save()
