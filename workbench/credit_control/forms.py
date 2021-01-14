import re

from django import forms
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext, gettext_lazy as _

from workbench.credit_control.models import CreditEntry, Ledger
from workbench.invoices.models import Invoice
from workbench.tools.formats import currency, local_date_format
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea


class CreditEntrySearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
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
        empty_label=_("All ledgers"),
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if data.get("s") == "pending":
            queryset = queryset.pending()
        elif data.get("s") == "processed":
            queryset = queryset.processed()
        queryset = self.apply_simple(queryset, "ledger")
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


class AccountStatementUploadForm(Form):
    ledger = CreditEntry._meta.get_field("ledger").formfield(widget=forms.RadioSelect)
    statement = forms.FileField(label=_("Account statement"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ledger"].choices = [
            (ledger.id, str(ledger)) for ledger in Ledger.objects.all()
        ]

    def clean(self):
        data = super().clean()
        if data.get("statement") and data.get("ledger"):
            try:
                self.statement_list = data["ledger"].parse_fn(data["statement"].read())
            except Exception as exc:
                raise forms.ValidationError(
                    _(
                        "Error while parsing the statement."
                        " Did you upload a valid CSV file? (Technical error: %s)"
                    )
                    % exc
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
        created_entries = []
        ledger = self.cleaned_data["ledger"]

        for data in reversed(self.statement_list):  # From past to present
            reference_number = data.pop("reference_number")

            c, created = ledger.transactions.get_or_create(
                reference_number=reference_number, defaults=data
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
                    '<a href="{}" target="_blank"'
                    ' rel="noopener noreferrer">{}, {}: {}</a>',
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
                                        "{}",
                                        invoice.contact.name_with_organization
                                        if invoice.contact
                                        else invoice.customer,
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
                                    format_html(
                                        "<br><span style='color:darkred'>{}: {}</span>",
                                        _("third party costs"),
                                        currency(invoice.third_party_costs),
                                    )
                                    if invoice.third_party_costs
                                    else "",
                                    "</span>",
                                )
                            )
                        ),
                    )
                    for invoice in Invoice.objects.open()
                    .filter(total=entry.total)
                    .select_related(
                        "contact__organization", "customer", "owned_by", "project"
                    )[:100]
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
