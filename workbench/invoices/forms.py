import datetime as dt
import io
from decimal import Decimal

from authlib.email import render_to_mail
from django import forms
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils.html import format_html, mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext, gettext_lazy as _
from django_fast_export.csv import StreamingCSVResponse, all_values, all_verbose_names

from workbench.accounts.models import User
from workbench.contacts.forms import PostalAddressSelectionForm
from workbench.contacts.models import Organization, Person
from workbench.invoices import sending
from workbench.invoices.models import (
    Invoice,
    RecurringInvoice,
    Service,
    service_surplus,
)
from workbench.logbook.models import LoggedCost, LoggedHours
from workbench.projects.forms import (
    add_delete_planned_work_field,
    discard_offers_in_preparation,
)
from workbench.reporting.models import FreezeDate
from workbench.reporting.utils import accepted_offers_by_project
from workbench.services.models import ServiceType
from workbench.tools.formats import Z1, Z2, currency, hours, local_date_format
from workbench.tools.forms import (
    Autocomplete,
    DateInput,
    Form,
    ModelForm,
    SuggestionsInput,
    Textarea,
    add_prefix,
)
from workbench.tools.pdf import PDFDocument, pdf_response
from workbench.tools.validation import in_days


class InvoiceSearchForm(Form):
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
            ("open", _("Open")),
            ("due", _("Due")),
            (_("Exact"), Invoice.STATUS_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    org = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Autocomplete(model=Organization),
        label="",
    )
    owned_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if data.get("s") == "open":
            queryset = queryset.open()
        elif data.get("s") == "due":
            queryset = queryset.due()
        elif data.get("s"):
            queryset = queryset.filter(status=data.get("s"))
        queryset = self.apply_renamed(queryset, "org", "customer")
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related(
            "customer", "contact__organization", "owned_by", "project__owned_by"
        )

    def response(self, request, queryset):
        if request.GET.get("export") == "pdf":
            if not queryset.exists():
                messages.warning(request, _("No invoices found."))
                return HttpResponseRedirect("?error=1")

            count = queryset.count()
            if count > settings.BATCH_MAX_ITEMS:
                messages.error(
                    request, _("%s invoices in selection, that's too many.") % count
                )
                return HttpResponseRedirect("?error=1")

            pdf, response = pdf_response(
                "invoices",
                as_attachment=request.GET.get("disposition") == "attachment",
            )
            for invoice in queryset:
                pdf.init_invoice_letter()
                pdf.process_invoice(invoice)
                pdf.restart()
            pdf.generate()
            return response

        if request.GET.get("export") == "xlsx":

            def generate():
                yield [
                    *all_verbose_names(queryset.model),
                    capfirst(gettext("project")),
                    capfirst(gettext("contact person")),
                    capfirst(gettext("type")),
                    capfirst(gettext("closed on")),
                ]
                yield from (
                    [
                        *all_values(invoice),
                        invoice.project.title if invoice.project else None,
                        invoice.project.owned_by if invoice.project else None,
                        invoice.project.get_type_display() if invoice.project else None,
                        invoice.project.closed_on if invoice.project else None,
                    ]
                    for invoice in queryset
                )

            return StreamingCSVResponse(generate(), filename="invoices.csv")
        return None


def warn_about_postponed_reminders(form, postpone):
    if postpone and postpone > in_days(Invoice.UNEXPECTED_POSTPONE_REMINDERS_DAYS):
        form.add_warning(
            _(
                "You are postponing reminders until %(date)s, which is more"
                " than %(days)s days from now. Are you sure?"
            )
            % {
                "date": local_date_format(postpone),
                "days": Invoice.UNEXPECTED_POSTPONE_REMINDERS_DAYS,
            },
            code="postpone-reminders-far-out",
        )


@add_prefix("modal")
class PostponeRemindersForm(ModelForm):
    """Postpones the reminders of a sent invoice without the validation of
    the whole invoice"""

    class Meta:
        model = Invoice
        fields = ["postpone_reminders_until"]

    def clean(self):
        data = super().clean()
        if self.instance._orig_status != Invoice.SENT:
            raise forms.ValidationError(
                _("Reminders can only be postponed for sent invoices.")
            )
        warn_about_postponed_reminders(self, data.get("postpone_reminders_until"))
        return data


@add_prefix("modal")
class SendInvoiceForm(ModelForm):
    """Releases an invoice in preparation: mails it with the PDF to the
    customer and marks it as sent, invoiced today and due in 15 days"""

    DUE_DAYS = 15

    class Meta:
        model = Invoice
        fields = ["invoiced_on", "due_on"]
        widgets = {"invoiced_on": DateInput, "due_on": DateInput}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        emails = sending.suggested_emails(self.instance)
        self.fields["email"] = forms.EmailField(
            label=_("recipient"),
            initial=emails[0] if emails else "",
            widget=SuggestionsInput(emails),
            help_text=_("The owner of the invoice gets a copy and the replies."),
        )
        self.fields["invoiced_on"].required = True
        self.fields["due_on"].required = True
        self.initial["invoiced_on"] = dt.date.today()
        self.initial["due_on"] = in_days(self.DUE_DAYS)
        subject, body = sending.proposal(self.instance, self.fields["email"].initial)
        self.fields["subject"] = forms.CharField(
            label=_("subject"), initial=subject, max_length=200
        )
        self.fields["body"] = forms.CharField(
            label=_("text"),
            initial=body,
            widget=Textarea({"rows": 12}),
            help_text=RecurringInvoice._meta.get_field("mail_body").help_text,
        )
        self.order_fields(["email", "invoiced_on", "due_on", "subject", "body"])

    def clean(self):
        data = super().clean()
        if self.instance._orig_status != Invoice.IN_PREPARATION:
            raise forms.ValidationError(_("Only invoices in preparation can be sent."))
        if (
            (invoiced_on := data.get("invoiced_on"))
            and (freeze := FreezeDate.objects.up_to())
            and invoiced_on <= freeze
        ):
            self.add_error(
                "invoiced_on",
                _(
                    "Cannot create an invoice with a date of {} or earlier anymore."
                ).format(local_date_format(freeze)),
            )
        elif invoiced_on and invoiced_on < in_days(-3):
            self.add_warning(
                _("The invoice date is in the past (%s). Are you sure?")
                % local_date_format(invoiced_on),
                code="invoiced-in-past",
            )
        if invoiced_on and (due_on := data.get("due_on")) and due_on < invoiced_on:
            self.add_error("due_on", _("Due date has to be after invoice date."))
        return data

    def mail(self):
        data = self.cleaned_data
        return sending.invoice_mail(
            self.instance, to=data["email"], subject=data["subject"], body=data["body"]
        )

    def save(self):
        data = self.cleaned_data
        sending.send(
            self.instance,
            to=data["email"],
            subject=data["subject"],
            body=data["body"],
            save=super().save,
        )
        return self.instance


@add_prefix("modal")
class SettleInvoiceForm(ModelForm):
    """Marks a sent invoice as paid or cancelled with only the fields which
    are needed (the invoice form works too)"""

    class Meta:
        model = Invoice
        fields = ["status", "closed_on", "payment_notice"]
        widgets = {
            "status": forms.RadioSelect,
            "payment_notice": Textarea({"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            row
            for row in Invoice.STATUS_CHOICES
            if row[0] in {Invoice.PAID, Invoice.CANCELED}
        ]
        if (status := self.request.GET.get("status", "")).isdigit():
            self.initial["status"] = int(status)
        elif self.instance.status not in {Invoice.PAID, Invoice.CANCELED}:
            self.initial["status"] = Invoice.PAID
        self.initial["closed_on"] = self.instance.closed_on or dt.date.today()

    def clean(self):
        data = super().clean()
        if self.instance._orig_status != Invoice.SENT:
            raise forms.ValidationError(_("Only sent invoices can be settled here."))
        if not data.get("closed_on"):
            data["closed_on"] = dt.date.today()
        if data.get("status") == Invoice.PAID and data["closed_on"] < in_days(-180):
            self.add_warning(
                _(
                    "You are setting the payment date to a value over 6 months ago. Are you sure?"
                ),
                code="paid-in-past",
            )
        if data.get("status") == Invoice.CANCELED and (
            final := self.instance.down_payment_applied_to
        ):
            # Like the invoice form: the final invoice deducts it
            if final.status > Invoice.IN_PREPARATION:
                self.add_error(
                    "status",
                    format_html(
                        "{} {}",
                        _(
                            "This down payment has been applied to an invoice,"
                            " cancel that invoice first:"
                        ),
                        final,
                    ),
                )
        return data


class InvoiceForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Invoice
        fields = (
            "contact",
            "customer",
            "invoiced_on",
            "due_on",
            "title",
            "description",
            "service_period_from",
            "service_period_until",
            "owned_by",
            "status",
            "closed_on",
            "payment_notice",
            "postal_address",
            "type",
            "subtotal",
            "third_party_costs",
            "discount",
            "liable_to_vat",
            "tax_rate",
            "show_service_details",
        )
        widgets = {
            "customer": Autocomplete(model=Organization),
            "contact": Autocomplete(model=Person, params={"only_employees": "on"}),
            "status": forms.RadioSelect,
            "description": Textarea,
            "payment_notice": Textarea({"rows": 2}),
            "postal_address": Textarea,
            "type": forms.RadioSelect,
            "tax_rate": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs["instance"]
        if instance.type == instance.CREDIT:
            kwargs.setdefault("initial", {})["subtotal"] = -instance.subtotal

        super().__init__(*args, **kwargs)

        self.fields["type"].choices = Invoice.TYPE_CHOICES
        self.fields["type"].disabled = True

        if self.instance.project:
            self.fields["customer"].disabled = True
            self.fields["customer"].help_text = _("Determined by project.")

        if self.instance.type == self.instance.DOWN_PAYMENT:
            self.fields["subtotal"].label = _("Down payment")
            self.fields.pop("service_period_from")
            self.fields.pop("service_period_until")

        if self.instance.type == self.instance.CREDIT:
            self.fields["subtotal"].label = _("Credit")
            self.fields.pop("service_period_from")
            self.fields.pop("service_period_until")
            self.fields.pop("third_party_costs")
            self.fields.pop("discount")

        if self.instance.type == self.instance.SERVICES:
            self.fields["subtotal"].disabled = True
            self.fields["third_party_costs"].disabled = True
            self.fields["subtotal"].help_text = _("Calculated from invoice services.")
            self.fields["third_party_costs"].help_text = _(
                "Calculated from invoice services."
            )

        else:
            self.fields.pop("show_service_details")

        if (
            self.instance.type not in {Invoice.DOWN_PAYMENT, Invoice.CREDIT}
            and self.instance.project_id
        ):
            eligible_down_payment_invoices = Invoice.objects.invoiced().filter(
                Q(project=self.instance.project),
                Q(type=Invoice.DOWN_PAYMENT),
                Q(down_payment_applied_to__isnull=True)
                | Q(down_payment_applied_to=self.instance.pk),
            )
            if eligible_down_payment_invoices:
                self.fields["apply_down_payment"] = forms.ModelMultipleChoiceField(
                    label=_("Apply down payment invoices"),
                    queryset=eligible_down_payment_invoices,
                    widget=forms.CheckboxSelectMultiple,
                    required=False,
                    initial=Invoice.objects.filter(
                        down_payment_applied_to=self.instance
                    ).values_list("id", flat=True)
                    if self.instance.pk
                    else [],
                )
                self.fields["apply_down_payment"].choices = [
                    (
                        invoice.id,
                        format_html(
                            "{}<br/>{}, {}",
                            invoice.__html__(),
                            invoice.pretty_total_excl,
                            invoice.pretty_status,
                        ),
                    )
                    for invoice in eligible_down_payment_invoices
                ]

        self.order_fields(
            field
            for field in list(self.fields)
            if field
            not in {
                "subtotal",
                "discount",
                "apply_down_payment",
                "liable_to_vat",
                "tax_rate",
                "show_service_details",
            }
        )

        self.add_postal_address_selection_if_empty(
            person=self.instance.contact,
            organization=self.instance.customer,
            for_billing=True,
        )

        if self.instance.is_freezed:
            if self.request.method == "GET":
                messages.warning(
                    self.request,
                    _(
                        "This invoice is freezed, only a small subset of fields are editable."
                    ),
                )

            for field in list(self.fields):
                if field not in {
                    "contact",
                    "customer",
                    "title",
                    "description",
                    "owned_by",
                    "postal_address",
                    "type",
                    "third_party_costs",
                    "status",
                    "payment_notice",
                }:
                    self.fields[field].disabled = True

            if self.instance.status == Invoice.SENT:
                self.fields["status"].choices = [
                    row
                    for row in Invoice.STATUS_CHOICES
                    if row[0] in {Invoice.SENT, Invoice.PAID, Invoice.CANCELED}
                ]
                self.fields["closed_on"].disabled = False
            else:
                self.fields.pop("status", None)
                self.fields.pop("closed_on", None)
                self.fields.pop("payment_notice", None)

    def _is_status_unexpected(self, to_status):
        from_status = self.instance._orig_status

        if from_status == to_status:
            return False
        return bool(from_status > to_status or from_status >= Invoice.PAID)

    def clean(self):  # noqa: C901
        data = super().clean()
        s_dict = dict(Invoice.STATUS_CHOICES)

        if (subtotal := data.get("subtotal")) and subtotal < 0:
            self.add_error(
                "subtotal",
                _(
                    "A negative subtotal is almost certainly an error. Did you want to create a credit?"
                ),
            )

        if (
            (
                "invoiced_on" in self.changed_data
                or (
                    "status" in self.changed_data
                    and self.instance._orig_status < self.instance.SENT
                )
            )
            and (invoiced_on := data.get("invoiced_on"))
            and (freeze := FreezeDate.objects.up_to())
            and invoiced_on <= freeze
        ):
            self.add_error(
                "invoiced_on",
                _(
                    "Cannot create an invoice with a date of {} or earlier anymore."
                ).format(local_date_format(freeze)),
            )

        if self.instance.status > self.instance.IN_PREPARATION and set(
            self.changed_data
        ) - {
            "status",
            "closed_on",
            "payment_notice",
            "third_party_costs",
        }:
            self.add_warning(
                _(
                    "You are attempting to change %(fields)s."
                    " I am trying to prevent unintentional changes."
                    " Are you sure?"
                )
                % {
                    "fields": ", ".join(
                        "'%s'" % self.fields[field].label for field in self.changed_data
                    )
                },
                code="maybe-unintentional-invoice-change",
            )

        # Freezed invoices to not have an editable status field.
        has_status = "status" in data

        if has_status and self._is_status_unexpected(data["status"]):
            self.add_warning(
                _("Moving status from '%(from)s' to '%(to)s'. Are you sure?")
                % {
                    "from": s_dict[self.instance._orig_status],
                    "to": s_dict[data["status"]],
                },
                code="status-unexpected",
            )

        if (
            has_status
            and self.instance._orig_status == Invoice.IN_PREPARATION
            and data["status"] > Invoice.IN_PREPARATION
            and data.get("invoiced_on")
            and data["invoiced_on"] < in_days(-3)
        ):
            self.add_warning(
                _(
                    "Moving status from '%(from)s' to '%(to)s' with an"
                    " invoice date in the past (%(date)s)."
                    " This may be correct but maybe it's not what you want."
                )
                % {
                    "from": s_dict[Invoice.IN_PREPARATION],
                    "to": s_dict[data["status"]],
                    "date": local_date_format(data["invoiced_on"]),
                },
                code="invoiced-in-past",
            )

        if (invoiced_on := data.get("invoiced_on")) and invoiced_on > in_days(90):
            self.add_warning(
                _(
                    "Attention! The invoice date is more than three months in the future!"
                ),
                code="invoiced-in-future",
            )

        if (
            has_status
            and self.instance._orig_status < Invoice.PAID
            and data["status"] == Invoice.PAID
            and (closed_on := data.get("closed_on"))
            and closed_on < in_days(-180)
        ):
            self.add_warning(
                _(
                    "You are setting the payment date to a value over 6 months ago. Are you sure?"
                ),
                code="paid-in-past",
            )

        if has_status and data["status"] >= Invoice.PAID and not data["closed_on"]:
            data["closed_on"] = dt.date.today()

        if has_status and self.instance.closed_on and data["status"] < Invoice.PAID:
            if self.should_ignore_warnings():
                data["closed_on"] = None
            else:
                self.add_warning(
                    _(
                        "You are attempting to set status to '%(to)s',"
                        " but the invoice has already been closed on %(closed)s."
                        " Are you sure?"
                    )
                    % {
                        "to": s_dict[data["status"]],
                        "closed": local_date_format(self.instance.closed_on),
                    },
                    code="status-change-but-already-closed",
                )

        if (
            data.get("liable_to_vat")
            and (tax_rate := data["tax_rate"])
            and (service_period_until := data.get("service_period_until"))
        ):
            if service_period_until >= dt.date(2024, 1, 1) and tax_rate == Decimal(
                "7.70"
            ):
                self.add_warning(
                    _(
                        "Are you sure the tax rate is correct? The service period extends into 2024 but you have selected the old tax rate."
                    ),
                    code="tax-rate",
                )
            if service_period_until < dt.date(2024, 1, 1) and tax_rate == Decimal(
                "8.10"
            ):
                self.add_warning(
                    _(
                        "Are you sure the tax rate is correct? The service period ends before 2024 but you have selected the new tax rate."
                    ),
                    code="tax-rate",
                )

        if (
            has_status
            and self.instance._orig_status == Invoice.IN_PREPARATION
            and data["status"] == Invoice.CANCELED
        ):
            # They would count as cancelled in the key data
            self.add_error(
                "status",
                _("Invoices which haven't been sent are deleted, not cancelled."),
            )

        if (
            final := self.instance.down_payment_applied_to
        ) and final.status > Invoice.IN_PREPARATION:
            # The final invoice deducts the down payment, it can neither be
            # cancelled nor change its amount (final invoices in preparation
            # follow, see save())
            fields = {"subtotal", "discount"} & set(self.changed_data)
            if has_status and data["status"] in {
                Invoice.IN_PREPARATION,
                Invoice.CANCELED,
            }:
                fields.add("status")
            for field in sorted(fields):
                self.add_error(
                    field,
                    format_html(
                        "{} {}",
                        _(
                            "This down payment has been applied to an invoice,"
                            " cancel that invoice first:"
                        ),
                        final,
                    ),
                )

        if (
            "status" in data
            and self.instance._orig_status == Invoice.CANCELED
            and data["status"] != Invoice.CANCELED
            and self.instance.down_payment_total
        ):
            self.add_error(
                "status",
                _(
                    "The down payments of this invoice have been released when"
                    " it was cancelled, create a new invoice instead."
                ),
            )

        if (
            "status" in data
            and self.instance._orig_status == Invoice.CANCELED
            and data["status"] != Invoice.CANCELED
            and self.instance.type == Invoice.SERVICES
            and self.instance.services.exists()
        ):
            # Which entries were released can't be told anymore
            self.add_error(
                "status",
                _(
                    "The logged hours and costs of this invoice have been"
                    " released when it was cancelled, create a new invoice"
                    " instead."
                ),
            )

        if down_payments := data.get("apply_down_payment"):
            # Lines of new services invoices are only created when saving
            subtotal = (
                data.get("subtotal")
                if self.instance.type == Invoice.FIXED
                else self.instance.subtotal
            )
            down_payment_total = sum(
                (invoice.total_excl_tax for invoice in down_payments), Z2
            )
            if (
                subtotal is not None
                and (self.instance.type == Invoice.FIXED or self.instance.pk)
                and subtotal - (data.get("discount") or Z2) < down_payment_total
            ):
                self.add_warning(
                    _(
                        "The down payments (%(down_payments)s) exceed this"
                        " invoice, its total would be negative."
                    )
                    % {"down_payments": currency(down_payment_total)},
                    code="down-payments-exceed-total",
                )

        return data

    def save(self):
        instance = super().save(commit=False)

        if instance.type in {instance.FIXED, instance.DOWN_PAYMENT}:
            instance.subtotal = self.cleaned_data["subtotal"]

        elif instance.type == instance.CREDIT:
            instance.subtotal = -self.cleaned_data["subtotal"]

        if "apply_down_payment" not in self.cleaned_data:
            # No down payments can be applied (anymore), release those which
            # aren't sent or paid anymore
            if instance.pk:
                instance.down_payment_invoices.update(down_payment_applied_to=None)
            instance.down_payment_total = Z2

        else:
            if not instance.pk:
                instance.save()

            instance.down_payment_invoices.set(
                self.cleaned_data.get("apply_down_payment")
            )
            instance.down_payment_total = sum(
                (
                    invoice.total_excl_tax
                    for invoice in self.cleaned_data.get("apply_down_payment")
                ),
                Z2,
            )

        if final := instance.down_payment_applied_to:
            # Only final invoices in preparation, see clean()
            if instance.status in {Invoice.IN_PREPARATION, Invoice.CANCELED}:
                instance.down_payment_applied_to = None
            instance.save()
            final.down_payment_total = sum(
                (
                    invoice.total_excl_tax
                    for invoice in final.down_payment_invoices.all()
                ),
                Z2,
            )
            final.save()
            return instance

        instance.save()
        return instance


class CreateProjectInvoiceForm(InvoiceForm):
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        type = kwargs["request"].GET.get("type")
        # Invoices for one offer (from the offer's menu) start with its title,
        # description and services
        self.offer = None
        if (
            type == Invoice.SERVICES
            and (offer := kwargs["request"].GET.get("offer", "")).isascii()
            and offer.isdigit()
        ):
            self.offer = self.project.offers.filter(pk=offer).first()
        kwargs["instance"] = Invoice(
            customer=self.project.customer,
            contact=self.project.contact,
            project=self.project,
            # Both titles, people remove what doesn't fit
            title=f"{self.project.title} - {self.offer.title}"
            if self.offer
            else self.project.title,
            description=(self.offer.description if self.offer else "")
            or self.project.description,
            type=type,
            third_party_costs=Z2
            if type in {Invoice.SERVICES, Invoice.CREDIT}
            else None,
            discount=self.offer.discount if self.offer else Z2,
        )

        super().__init__(*args, **kwargs)

        # Hide those fields when creating invoices
        self.fields["status"].disabled = True
        self.fields["closed_on"].disabled = True

        invoice_type = self.request.GET.get("type")
        self.fields["type"].initial = self.instance.type = invoice_type

        if invoice_type == "services":
            self.add_services_field()
            self.fields.pop("service_period_from")
            self.fields.pop("service_period_until")

        if self.instance.type in {self.instance.DOWN_PAYMENT, self.instance.FIXED}:
            project = self.instance.project
            accepted = accepted_offers_by_project([project.pk])[project.pk]["total"]
            self.fields["subtotal"].help_text = mark_safe(
                _(
                    "Total excl. tax of accepted offers: {accepted}. Use {percentages}."
                ).format(
                    accepted=currency(accepted),
                    percentages=mark_safe(
                        ", ".join(
                            f'<a href="#" data-field-value="{(accepted / 100 * percentage).quantize(Z2)}">{percentage}%</a>'
                            for percentage in (50, 100)
                        )
                    ),
                )
            )

        if self.request.method == "GET" and (
            warnings := self.project.create_invoice_warnings(invoice_type)
        ):
            for _code, warning in warnings:
                messages.warning(self.request, warning)

        if not self.project.closed_on:
            self.fields["close_project"] = forms.BooleanField(
                label=_("This is the final invoice, close the project"),
                help_text=_(
                    "You'll still be able to log hours for a few days."
                    " You can always reopen the project later."
                ),
                required=False,
            )
            if self.is_bound and self.data.get(self.add_prefix("close_project")):
                add_delete_planned_work_field(self, self.project)

    # Fields of each service, named "<field>_<service ID>"
    SERVICE_ROW_FIELDS = [
        "source",
        "title",
        "description",
        "effort_type",
        "effort_hours",
        "effort_rate",
        "cost",
        "disable_logging",
    ]

    def add_services_field(self):  # noqa: C901
        source = (
            Invoice.LOGBOOK
            if self.request.GET.get("source") == "logbook"
            else Invoice.OFFER
        )
        # Invoicing from the offer links the logged entries too, the cutoff
        # date only applies to invoicing from the logbook
        self.fields["logbook_cutoff_date"] = forms.DateField(
            widget=DateInput,
            required=False,
            label=_("Logbook cutoff date"),
            help_text=_(
                "Only include logbook entries up to this date when invoicing"
                " the logbook or the surplus. The amounts shown below may be"
                " too high if using this."
            ),
        )

        def logged(row):
            if row["service"].effort_rate is None and row["not_archived_logged_hours"]:
                return format_html(
                    '{} <small class="bg-warning px-1">{}</small>',
                    currency(row["not_archived"]),
                    _("%s logged but no hourly rate defined.")
                    % hours(row["not_archived_logged_hours"]),
                )
            if row["not_archived_logged_hours"]:
                return format_html(
                    "{} ({})",
                    currency(row["not_archived"]),
                    hours(row["not_archived_logged_hours"]),
                )
            return currency(row["not_archived"])

        # Services which have been invoiced from the offer may have a surplus
        from_offer = set(
            Service.objects
            .filter(
                project_service__project=self.project,
                from_offer=True,
            )
            .exclude(invoice__status=Invoice.CANCELED)
            .values_list("project_service", flat=True)
        )

        choices = []
        selected = []
        self.service_groups = []
        # Offers for the filter above the form, which preselects their services
        # and only lists them unless all services of the project are wanted
        self.offer_filter = []
        show_all = self.request.GET.get("all") == "1"
        params = self.request.GET.copy()
        if show_all:
            params.pop("all")
        else:
            params["all"] = "1"
        self.toggle_all_url = f"?{params.urlencode()}"
        self.showing_all = show_all
        for offer, offer_data in self.project.grouped_services["offers"]:
            # Invoicing from the logbook lists what hasn't been invoiced yet
            rows = [
                row
                for row in offer_data["services"]
                if source == Invoice.OFFER
                or row["not_archived"]
                or row["not_archived_logged_hours"]
            ]
            # All offers with services, whatever the source; selecting one
            # without anything to invoice preselects nothing
            if offer and offer_data["services"]:
                self.offer_filter.append((offer, offer == self.offer))
            if self.offer and offer == self.offer:
                # Optional services haven't been ordered, unless work has
                # been logged on them
                selected = [
                    row["service"].id
                    for row in rows
                    if source == Invoice.LOGBOOK or not row["service"].is_optional
                ]
            elif self.offer and not show_all:
                continue
            if not rows:
                continue

            choices.append((
                str(offer or _("Not offered yet")),
                [(row["service"].id, row["service"].title) for row in rows],
            ))
            group = {"offer": offer, "rows": [], "has_surplus": False}
            self.service_groups.append(group)
            for row in rows:
                service = row["service"]
                sources = [
                    (
                        Invoice.OFFER,
                        format_html(
                            "{}: {}", _("as offered"), currency(service.service_cost)
                        ),
                    ),
                    (
                        Invoice.LOGBOOK,
                        format_html("{}: {}", _("as logged"), logged(row)),
                    ),
                ]
                if service.id in from_offer:
                    group["has_surplus"] = True
                    surplus = service_surplus(service)
                    sources.append((
                        Invoice.SURPLUS,
                        format_html(
                            "{}: {}",
                            _("surplus"),
                            currency(
                                surplus["hours"] * (service.effort_rate or Z2)
                                + surplus["cost"]
                            ),
                        ),
                    ))
                self.fields[f"source_{service.id}"] = forms.ChoiceField(
                    label=_("invoicing"),
                    choices=sources,
                    initial=source,
                    widget=forms.RadioSelect,
                    required=False,
                )
                self.fields[f"disable_logging_{service.id}"] = forms.BooleanField(
                    label=_("disable logging"),
                    required=False,
                )
                # The line's texts and amounts, empty fields are taken from
                # the service and the source
                for field, initial in [
                    ("title", service.title),
                    ("description", service.description),
                    ("effort_type", service.effort_type),
                    ("effort_hours", None),
                    ("effort_rate", service.effort_rate),
                    ("cost", None),
                ]:
                    self.fields[f"{field}_{service.id}"] = Service._meta.get_field(
                        field
                    ).formfield(required=False, initial=initial)
                # What the sources would invoice, for placeholders
                presets = {
                    Invoice.OFFER: (service.effort_hours, service.cost),
                    Invoice.LOGBOOK: (
                        row["not_archived_logged_hours"],
                        row["not_archived_logged_cost"],
                    ),
                }
                if service.id in from_offer:
                    presets[Invoice.SURPLUS] = (surplus["hours"], surplus["cost"])
                group["rows"].append({
                    "service": service,
                    "presets": {
                        key: {"hours": hours or Z1, "cost": cost or Z2}
                        for key, (hours, cost) in presets.items()
                    },
                    **{
                        field: f"{field}_{service.id}"
                        for field in self.SERVICE_ROW_FIELDS
                    },
                })

        self.fields["selected_services"] = forms.TypedMultipleChoiceField(
            choices=choices,
            coerce=int,
            initial=selected,
            label=_("services"),
            widget=forms.CheckboxSelectMultiple,
        )
        self.service_fields = [
            "selected_services",
            *(
                row[field]
                for group in self.service_groups
                for row in group["rows"]
                for field in self.SERVICE_ROW_FIELDS
            ),
        ]
        # The template renders them as a table
        self.service_fields_exclude = ",".join(self.service_fields)
        checkboxes = {
            widget.data["value"]: widget for widget in self["selected_services"]
        }
        for group in self.service_groups:
            for row in group["rows"]:
                row["selected"] = checkboxes[row["service"].id]
                for field in self.SERVICE_ROW_FIELDS:
                    row[field] = self[row[field]]
                # The source shown, to show its amounts as placeholders
                preset = row["presets"].get(row["source"].value()) or next(
                    iter(row["presets"].values())
                )
                row["effort_hours"].field.widget.attrs["placeholder"] = preset["hours"]
                row["cost"].field.widget.attrs["placeholder"] = preset["cost"]
                row["options"] = [
                    (radio, row["presets"][radio.data["value"]])
                    for radio in row["source"]
                ]

    def service_sources(self):
        """The source of each selected service, the default (from the menu
        entry) if none was given"""
        default = (
            Invoice.LOGBOOK
            if self.request.GET.get("source") == "logbook"
            else Invoice.OFFER
        )
        return {
            id: self.cleaned_data.get(f"source_{id}") or default
            for id in self.cleaned_data.get("selected_services") or ()
        }

    def clean(self):
        data = super().clean()
        if "selected_services" in data:
            sources = self.service_sources()
            # Invoicing new work from the logbook again is the normal case,
            # the danger is switching between the offer and the logbook
            lines = Service.objects.filter(
                invoice__status__in=[
                    Invoice.IN_PREPARATION,
                    Invoice.SENT,
                    Invoice.PAID,
                ],
            )
            for source, message in [
                (
                    Invoice.LOGBOOK,
                    _(
                        "Some services have been invoiced from the offer already:"
                        " %(services)s. Make sure the same work isn't invoiced"
                        " twice, or only invoice the surplus."
                    ),
                ),
                (
                    Invoice.OFFER,
                    _(
                        "Some services have been invoiced already: %(services)s."
                        " Make sure the same work isn't invoiced twice."
                    ),
                ),
            ]:
                invoiced = self.project.services.filter(
                    id__in=[id for id, s in sources.items() if s == source],
                    invoice_services__in=lines.filter(from_offer=True)
                    if source == Invoice.LOGBOOK
                    else lines,
                ).distinct()
                if invoiced:
                    self.add_warning(
                        message
                        % {
                            "services": ", ".join(service.title for service in invoiced)
                        },
                        code="services-invoiced-already",
                    )
        return data

    def save(self):
        if self.request.GET.get("type") == "services":
            instance = super().save()
            sources = self.service_sources()
            services = self.project.services.filter(id__in=sources).select_related(
                "offer"
            )
            instance.create_services(
                services,
                sources=sources,
                logbook_cutoff_date=self.cleaned_data.get("logbook_cutoff_date"),
                overrides={
                    id: {
                        field: value
                        for field in [
                            "title",
                            "description",
                            "effort_type",
                            "effort_hours",
                            "effort_rate",
                            "cost",
                        ]
                        if (value := self.cleaned_data.get(f"{field}_{id}"))
                        not in {None, ""}
                    }
                    for id in sources
                },
            )
            services.filter(
                id__in=[
                    id
                    for id in sources
                    if self.cleaned_data.get(f"disable_logging_{id}")
                ]
            ).update(allow_logging=False)

        else:
            instance = super().save()

        if self.cleaned_data.get("close_project"):
            self.project.closed_on = dt.date.today()
            self.project.save()
            discard_offers_in_preparation(
                self.project,
                request=self.request,
                delete_planned_work=self.cleaned_data.get("delete_planned_work"),
            )

        return instance


class CreatePersonInvoiceForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ("owned_by",)
    type = forms.ChoiceField(
        label=_("type"),
        choices=Invoice.TYPE_CHOICES,
        initial=Invoice.FIXED,
        disabled=True,
        widget=forms.RadioSelect,
        help_text=_("Other invoice types must be created directly on a project."),
    )

    class Meta:
        model = Invoice
        fields = (
            "contact",
            "customer",
            "invoiced_on",
            "due_on",
            "title",
            "description",
            "service_period_from",
            "service_period_until",
            "owned_by",
            "postal_address",
            "subtotal",
            "third_party_costs",
            "discount",
            "liable_to_vat",
            "tax_rate",
        )
        widgets = {
            "customer": Autocomplete(model=Organization),
            "contact": Autocomplete(model=Person, params={"only_employees": "on"}),
            "description": Textarea,
            "postal_address": Textarea,
            "tax_rate": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        request = kwargs["request"]
        initial = kwargs.setdefault("initial", {})
        initial.update(
            {"subtotal": None, "third_party_costs": None}  # Invalid -- force input.
        )

        contact = None
        customer = None
        self.pre_form = False

        if pk := request.GET.get("contact"):
            try:
                contact = Person.objects.get(pk=pk)
            except Person.DoesNotExist, TypeError, ValueError:
                self.pre_form = True
            else:
                initial.update({"customer": contact.organization, "contact": contact})

        elif pk := request.GET.get("customer"):
            try:
                customer = Organization.objects.get(pk=pk)
            except Organization.DoesNotExist, TypeError, ValueError:
                self.pre_form = True
            else:
                initial.update({"customer": customer})

        else:
            self.pre_form = True

        super().__init__(*args, **kwargs)

        self.instance.type = Invoice.FIXED

        if self.pre_form:
            for field in list(self.fields):
                if field not in {"customer", "contact"}:
                    self.fields.pop(field)
        else:
            self.add_postal_address_selection_if_empty(
                person=contact, organization=customer, for_billing=True
            )


class InvoiceDeleteForm(ModelForm):
    class Meta:
        model = Invoice
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.instance.status <= self.instance.IN_PREPARATION, (
            "Trying to delete an invoice not in preparation"
        )
        if (
            LoggedHours.objects.filter(invoice_service__invoice=self.instance).exists()
            or LoggedCost.objects.filter(
                invoice_service__invoice=self.instance
            ).exists()
        ):
            self.add_warning(
                _(
                    "Logged services are linked with this invoice."
                    " They will be released when deleting this invoice."
                ),
                code="release-logged-services",
            )

        if self.instance.down_payment_invoices.exists():
            self.add_warning(
                _(
                    "Down payment invoices are subtracted from this invoice."
                    " Those down payments will be released when deleting this"
                    " invoice."
                ),
                code="release-down-payments",
            )

    def delete(self):
        self.instance._unlink_logbook()
        self.instance._unlink_down_payments()
        self.instance.delete()


class ServiceForm(ModelForm):
    service_type = forms.ModelChoiceField(
        ServiceType.objects.all(),
        label=ServiceType._meta.verbose_name,
        required=False,
        help_text=_("Optional, but useful for quickly filling the fields below."),
    )

    class Meta:
        model = Service
        fields = [
            "title",
            "description",
            "effort_type",
            "effort_hours",
            "effort_rate",
            "cost",
            "third_party_costs",
        ]
        widgets = {"description": Textarea}

    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop("invoice", None) or kwargs["instance"].invoice
        super().__init__(*args, **kwargs)
        self.instance.invoice = self.invoice

    def clean(self):
        data = super().clean()
        # Updating and deleting is refused by Service.allow_update
        if self.invoice.status > Invoice.IN_PREPARATION:
            raise forms.ValidationError(
                _(
                    "Cannot modify a service bound to an invoice"
                    " which is not in preparation anymore."
                )
            )
        return data


class RecurringInvoiceSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=(("all", _("All states")), ("", _("Open")), ("closed", _("Closed"))),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    org = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Autocomplete(model=Organization),
        label="",
    )
    owned_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if not data.get("s"):
            queryset = queryset.open()
        elif data.get("s") == "closed":
            queryset = queryset.closed()
        queryset = self.apply_renamed(queryset, "org", "customer")
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related("customer", "contact__organization", "owned_by")


class RecurringInvoiceForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = RecurringInvoice
        fields = (
            "contact",
            "customer",
            "title",
            "description",
            "owned_by",
            "postal_address",
            "starts_on",
            "ends_on",
            "periodicity",
            "create_invoice_on_day",
            "next_period_starts_on",
            "subtotal",
            "third_party_costs",
            "discount",
            "liable_to_vat",
            "create_project",
            "new_invoices",
            "send_to",
            "mail_subject",
            "mail_body",
        )
        widgets = {
            "customer": Autocomplete(model=Organization),
            "contact": Autocomplete(model=Person, params={"only_employees": "on"}),
            "description": Textarea,
            "postal_address": Textarea,
            "periodicity": forms.RadioSelect,
            "new_invoices": forms.RadioSelect,
            "mail_body": Textarea({"rows": 12}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        contact = None
        customer = None
        self.pre_form = False
        request = kwargs["request"]
        initial = kwargs.setdefault("initial", {})

        if pk := request.GET.get("copy"):
            try:
                invoice = RecurringInvoice.objects.get(pk=pk)
            except RecurringInvoice.DoesNotExist, TypeError, ValueError:
                pass
            else:
                initial.update({
                    "customer": invoice.customer_id,
                    "contact": invoice.contact_id,
                    "title": invoice.title,
                    "description": invoice.description,
                    "owned_by": invoice.owned_by_id,
                    "postal_address": invoice.postal_address,
                    "periodicity": invoice.periodicity,
                    "create_invoice_on_day": invoice.create_invoice_on_day,
                    "subtotal": invoice.subtotal,
                    "discount": invoice.discount,
                    "third_party_costs": invoice.third_party_costs,
                    "liable_to_vat": invoice.liable_to_vat,
                })

        elif pk := request.GET.get("contact"):
            try:
                contact = Person.objects.get(pk=pk)
            except Person.DoesNotExist, TypeError, ValueError:
                self.pre_form = True
            else:
                initial.update({"customer": contact.organization, "contact": contact})

        elif pk := request.GET.get("customer"):
            try:
                customer = Organization.objects.get(pk=pk)
            except Organization.DoesNotExist, TypeError, ValueError:
                self.pre_form = True
            else:
                initial.update({"customer": customer})

        elif not instance:
            self.pre_form = True

        if not self.pre_form and not instance:
            kwargs["instance"] = RecurringInvoice(subtotal=None, third_party_costs=None)

        super().__init__(*args, **kwargs)

        if self.pre_form:
            for field in list(self.fields):
                if field not in {"customer", "contact"}:
                    self.fields.pop(field)

        else:
            self.fields["periodicity"].choices = RecurringInvoice.PERIODICITY_CHOICES
            self.fields["next_period_starts_on"].disabled = True

            self.add_postal_address_selection_if_empty(
                person=self.instance.contact or contact,
                organization=customer,
                for_billing=True,
            )
            self.propose_mail()

    def propose_mail(self):
        """Suggests recipients and proposes the mail for sending by email
        once the recurring invoice has a customer"""
        if not self.instance.customer_id:
            return
        emails = sending.suggested_emails(self.instance)
        self.fields["send_to"].widget = SuggestionsInput(emails)
        if emails and not self.instance.send_to:
            self.initial["send_to"] = emails[0]
        if not (self.instance.mail_subject and self.instance.mail_body):
            subject, body = sending.recurring_proposal(
                self.instance, self.initial.get("send_to") or self.instance.send_to
            )
            self.initial["mail_subject"] = self.instance.mail_subject or subject
            self.initial["mail_body"] = self.instance.mail_body or body

    def clean_mail(self, data):
        """Fills in the recipient and the proposal for sending by email,
        e.g. for new recurring invoices"""
        if data.get("new_invoices") != RecurringInvoice.SEND or not (
            customer := data.get("customer")
        ):
            return
        recurring_invoice = RecurringInvoice(
            customer=customer,
            contact=data.get("contact"),
            title=data.get("title", ""),
            owned_by=data.get("owned_by") or self.request.user,
            subtotal=data.get("subtotal") or 0,
            discount=data.get("discount") or 0,
            liable_to_vat=data.get("liable_to_vat", True),
        )
        if not data.get("send_to"):
            emails = sending.suggested_emails(recurring_invoice)
            if not emails:
                self.add_error("send_to", _("No email address."))
                return
            data["send_to"] = emails[0]
        if not (data.get("mail_subject") and data.get("mail_body")):
            subject, body = sending.recurring_proposal(
                recurring_invoice, data["send_to"]
            )
            data["mail_subject"] = data.get("mail_subject") or subject
            data["mail_body"] = data.get("mail_body") or body

    def clean(self):
        data = super().clean()
        self.clean_mail(data)
        if (
            "starts_on" in self.changed_data
            and (starts_on := data.get("starts_on"))
            and (freeze := FreezeDate.objects.up_to())
            and starts_on <= freeze
        ):
            self.add_error(
                "starts_on",
                _(
                    "Cannot create a recurring invoice with a start date of {} or earlier anymore."
                ).format(local_date_format(freeze)),
            )

        if (
            self.instance.pk
            and "ends_on" in self.changed_data
            and self.instance.next_period_starts_on
            and not self.errors
        ):
            self.instance.ends_on = data.get("ends_on")
            self.instance.periodicity = data.get("periodicity")
            self.instance.create_invoice_on_day = data.get("create_invoice_on_day")
            if len(periods := self.instance.pending_periods()) > 1:
                self.add_warning(
                    _(
                        "This creates %(count)s invoices for the periods since"
                        " %(date)s. If the time in between shouldn't be invoiced,"
                        " leave this recurring invoice ended and create a new one."
                    )
                    % {
                        "count": len(periods),
                        "date": local_date_format(periods[0][0]),
                    },
                    code="recurring-invoice-backlog",
                )

        return data


class SendReminderForm(Form):
    def __init__(self, *args, **kwargs):
        self.contact = kwargs.pop("contact")
        super().__init__(*args, **kwargs)

        self.invoices = (
            Invoice.objects
            .overdue()
            .filter(contact=self.contact)
            .select_related("customer", "contact__organization", "owned_by", "project")
        )
        organization = self.contact.organization
        self.emails = list(
            dict.fromkeys(
                filter(
                    None,
                    [
                        organization and organization.accounts_payable_email,
                        *self.contact.emailaddresses.values_list("email", flat=True),
                        organization and organization.email,
                    ],
                )
            )
        )

        self.fields["email"] = forms.EmailField(label=_("email"))

    def recipients(self, to):
        """The recipient, the owners of the invoices and the sender in copy"""
        return {
            "to": [to],
            "cc": sorted({
                invoice.owned_by.email
                for invoice in self.invoices
                if invoice.owned_by.is_active
            }),
            "bcc": [
                email
                for email in [
                    self.request.user.email,
                    settings.WORKBENCH.REMINDER_FROM_EMAIL,
                ]
                if email
            ],
        }

    def process(self):
        mail = render_to_mail(
            "invoices/reminder_mail",
            {"WORKBENCH": settings.WORKBENCH},
            from_email=settings.WORKBENCH.REMINDER_FROM_EMAIL,
            **self.recipients(self.cleaned_data["email"]),
        )
        with io.BytesIO() as buf:
            pdf = PDFDocument(buf)
            pdf.dunning_letter(invoices=self.invoices)
            pdf.generate()
            mail.attach("Zahlungserinnerung.pdf", buf.getvalue(), "application/pdf")
        mail.send()

        self.invoices.update(last_reminded_on=dt.date.today())
