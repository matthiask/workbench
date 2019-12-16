import datetime as dt
import json
import re

from django import forms
from django.db.models import Q
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext, gettext_lazy as _

from workbench.credit_control.models import CreditEntry, Ledger
from workbench.invoices.models import Invoice
from workbench.tools.formats import currency, local_date_format
from workbench.tools.forms import Autocomplete, ModelForm, Textarea, WarningsForm


class CreditEntrySearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=(
            ("", _("All states")),
            ("pending", _("Pending")),
            ("processed", _("Processed")),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )
    ledger = forms.ModelChoiceField(
        Ledger.objects.all(),
        required=False,
        empty_label=_("all ledgers"),
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s") == "pending":
            queryset = queryset.filter(Q(invoice__isnull=True) & Q(notes=""))
        elif data.get("s") == "processed":
            queryset = queryset.filter(~Q(invoice__isnull=True) | ~Q(notes=""))
        if data.get("ledger"):
            queryset = queryset.filter(ledger=data["ledger"])
        return queryset.select_related(
            "invoice__project", "invoice__owned_by", "ledger"
        )


class CreditEntryForm(ModelForm):
    class Meta:
        model = CreditEntry
        fields = [
            "ledger",
            "reference_number",
            "value_date",
            "total",
            "payment_notice",
            "invoice",
            "notes",
        ]
        widgets = {"invoice": Autocomplete(model=Invoice), "notes": Textarea}

    def save(self):
        instance = super().save()
        if instance.invoice and instance.invoice.status != instance.invoice.PAID:
            instance.invoice.status = instance.invoice.PAID
            instance.invoice.closed_on = instance.value_date
            instance.invoice.payment_notice = instance.payment_notice
            instance.invoice.save()
        return instance


class AccountStatementUploadForm(WarningsForm, forms.Form):
    ledger = CreditEntry._meta.get_field("ledger").formfield(widget=forms.RadioSelect)
    statement = forms.FileField(label=_("account statement"))
    statement_data = forms.CharField(
        label=_("statement data"),
        help_text=_(
            "Automatically filled in when submitting a parseable account statement."
        ),
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields["ledger"].choices = [
            (ledger.id, str(ledger)) for ledger in Ledger.objects.all()
        ]

        if self.request.POST.get("statement_data") or self.request.FILES:
            self.fields["statement"].required = False
        else:
            self.fields["statement_data"].required = False

    def clean(self):
        data = super().clean()
        if data.get("statement") and data.get("ledger"):
            self.data = self.data.copy()
            self.statement_list = data["ledger"].parse_fn(data["statement"].read())
            self.data["statement_data"] = json.dumps(
                self.statement_list, sort_keys=True
            )

            reference_numbers = [
                entry["reference_number"] for entry in self.statement_list
            ]

            if (
                reference_numbers
                and not CreditEntry.objects.filter(
                    ledger=data["ledger"], reference_number__in=reference_numbers
                ).exists()
            ):
                self.add_warning(
                    _(
                        "The uploaded list only contains new payments."
                        " This is somewhat surprising if you exported"
                        " the list from the correct bank account.",
                    ),
                    code="no-known-payments",
                )

        return data

    def save(self):
        entries = json.loads(self.cleaned_data["statement_data"])

        created_entries = []
        for data in entries:
            reference_number = data.pop("reference_number")
            data["value_date"] = dt.datetime.strptime(
                data["value_date"], "%Y-%m-%d"
            ).date()
            c, created = CreditEntry.objects.get_or_create(
                ledger=self.cleaned_data["ledger"],
                reference_number=reference_number,
                defaults=data,
            )
            if created:
                created_entries.append(c)
        return created_entries


class AssignCreditEntriesForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")

        super().__init__(*args, **kwargs)

        self.entries = []
        for entry in CreditEntry.objects.reverse().filter(
            invoice__isnull=True, notes=""
        )[:20]:
            self.fields["entry_{}_invoice".format(entry.pk)] = forms.TypedChoiceField(
                label=format_html(
                    '<a href="{}" target="_blank">{}, {}: {}</a>',
                    entry.get_absolute_url(),
                    entry.total,
                    local_date_format(entry.value_date),
                    entry.payment_notice,
                ),
                choices=[(None, "----------")]
                + [
                    (
                        invoice.id,
                        mark_safe(
                            " ".join(
                                (
                                    format_html(
                                        '<span title="{}">', invoice.description
                                    ),
                                    format_html(
                                        "<strong>{}</strong>"
                                        if re.search(
                                            r"\b" + invoice.code + r"\b",
                                            entry.payment_notice,
                                        )
                                        else "{}",
                                        invoice,
                                    ),
                                    invoice.status_badge,
                                    "<br>",
                                    format_html(
                                        "{}", invoice.contact or invoice.customer
                                    ),
                                    "<br>",
                                    format_html(
                                        "{} {}",
                                        _("invoiced on"),
                                        local_date_format(invoice.invoiced_on),
                                    )
                                    if invoice.invoiced_on
                                    else gettext("NO DATE YET"),
                                    "<br>",
                                    currency(invoice.total),
                                    "</span>",
                                )
                            )
                        ),
                    )
                    for invoice in Invoice.objects.filter(
                        status__in=(Invoice.IN_PREPARATION, Invoice.SENT),
                        total=entry.total,
                    ).select_related(
                        "contact__organization", "customer", "owned_by", "project"
                    )[
                        :100
                    ]
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
