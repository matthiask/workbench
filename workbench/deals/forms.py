import datetime as dt

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.deals.models import (
    Attribute,
    AttributeGroup,
    Deal,
    DealAttribute,
    Value,
    ValueType,
)
from workbench.tools.formats import Z2
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea
from workbench.tools.validation import in_days
from workbench.tools.xlsx import WorkbenchXLSXDocument


class DealSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=(
            ("all", _("All states")),
            ("", _("Open")),
            (
                _("Closed"),
                [row for row in Deal.STATUS_CHOICES if not row[0] == Deal.OPEN],
            ),
            (
                _("Defined search"),
                [
                    ("archived-valuetypes", _("Deals with archived value types")),
                ],
            ),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
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
        queryset = queryset.search(data.get("q"))
        self.should_group_deals = False
        if data.get("s") == "":
            queryset = queryset.filter(status=Deal.OPEN).order_by(
                "-probability", "status", "decision_expected_on", "id"
            )
            self.should_group_deals = True
        elif data.get("s") == "archived-valuetypes":
            queryset = queryset.with_archived_valuestypes()
        elif data.get("s") != "all":
            queryset = queryset.filter(status=data.get("s")).order_by(
                "-closed_on", "-pk"
            )
        queryset = self.apply_renamed(queryset, "org", "customer")
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related("owned_by", "customer", "contact__organization")

    def response(self, request, queryset):
        if request.GET.get("export") == "xlsx":
            xlsx = WorkbenchXLSXDocument()
            additional = []
            values = {
                (v.deal_id, v.type_id): v.value
                for v in Value.objects.filter(deal__in=queryset)
            }
            attributes = {
                (a.deal_id, a.attribute.group_id): a.attribute
                for a in DealAttribute.objects.filter(deal__in=queryset).select_related(
                    "attribute"
                )
            }

            for vt in ValueType.objects.all():
                additional.append(
                    (
                        f"{Value._meta.verbose_name}: {vt}",
                        (lambda id: lambda deal: values.get((deal.id, id)))(vt.id),
                    )
                )
            for ag in AttributeGroup.objects.all():
                additional.append(
                    (
                        f"{Attribute._meta.verbose_name}: {ag}",
                        (lambda id: lambda deal: attributes.get((deal.id, id)))(ag.id),
                    )
                )
            xlsx.table_from_queryset(queryset, additional=additional)
            return xlsx.to_response("deals.xlsx")


def warn_if_not_in_preparation(form):
    if form.instance.closed_on and form.request.method == "GET":
        messages.warning(
            form.request,
            _(
                "This deal is already closed."
                " I assume you know what you're doing and wont stand in the way."
            ),
        )


class DealForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Deal
        fields = (
            "contact",
            "customer",
            "title",
            "description",
            "probability",
            "decision_expected_on",
            "owned_by",
        )
        widgets = {
            "customer": Autocomplete(model=Organization),
            "contact": Autocomplete(model=Person, params={"only_employees": "on"}),
            "probability": forms.RadioSelect,
            "description": Textarea,
        }

    def __init__(self, *args, **kwargs):
        request = kwargs["request"]
        if not kwargs.get("instance"):
            initial = kwargs.setdefault("initial", {})

        if pk := request.GET.get("contact"):
            try:
                contact = Person.objects.get(pk=pk)
            except (Person.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update({"customer": contact.organization, "contact": contact})

        elif pk := request.GET.get("customer"):
            try:
                customer = Organization.objects.get(pk=pk)
            except (Organization.DoesNotExist, TypeError, ValueError):
                pass
            else:
                initial.update({"customer": customer})

        super().__init__(*args, **kwargs)
        warn_if_not_in_preparation(self)

        field = Value._meta.get_field("value")
        values = (
            {v.type_id: v.value for v in self.instance.values.all()}
            if self.instance.pk
            else {}
        )
        for vt in ValueType.objects.all():
            key = f"value_{vt.id}"

            if vt.is_archived and vt.id not in values:
                continue

            postfix = ", {}".format(_("archived value type")) if vt.is_archived else ""
            self.fields[key] = field.formfield(
                label="%s (%s%s)"
                % (
                    vt.title,
                    _("Total %(currency)s") % {"currency": settings.WORKBENCH.CURRENCY},
                    postfix,
                ),
                required=False,
                initial=values.get(vt.id),
            )

        attributes = (
            {a.group_id: a.id for a in self.instance.attributes.all()}
            if self.instance.id
            else {}
        )
        for group in AttributeGroup.objects.all():
            key = f"attribute_{group.id}"
            if group.is_archived and group.id not in attributes:
                continue

            self.fields[key] = forms.ModelChoiceField(
                queryset=group.attributes.all(),
                required=group.is_required,
                label=group.title,
                widget=forms.RadioSelect,
                initial=attributes.get(group.id),
            )
            self.fields[key].choices = [
                (a.id, str(a))
                for a in group.attributes.active(include=attributes.get(group.id))
            ]

        self.fields["decision_expected_on"].help_text = format_html(
            "{} {}",
            _("Expected"),
            format_html_join(
                ", ",
                '<a href="#" data-field-value="{}">{}</a>',
                [
                    (in_days(7).isoformat(), _("in one week")),
                    (in_days(30).isoformat(), _("in one month")),
                    (in_days(60).isoformat(), _("in two months")),
                    (in_days(90).isoformat(), _("in three months")),
                ],
            ),
        )

        q = Q(is_active=True)
        if self.instance.pk:
            q |= Q(id__in=self.instance.contributors.values_list("id", flat=True))

        weights = (
            dict(self.instance.contributions.values_list("user_id", "weight"))
            if self.instance.pk
            else {request.user.pk: 100}
        )

        contribution_select_fields = []
        for user in User.objects.filter(q):
            name = f"user_{user.id}_contribution"
            self.fields[name] = forms.TypedChoiceField(
                label=user.get_full_name(),
                widget=ContributionSelect,
                choices=[
                    (0, _("normal")),
                    (50, _("contributing force")),
                    (100, _("main driving force")),
                ],
                initial=weights.get(user.id, 0),
                coerce=int,
                required=False,
            )
            contribution_select_fields.append(name)
        self.contribution_select_fields = ",".join(contribution_select_fields)

        self.fields["probability"].choices = self.fields["probability"].choices[1:]

    def clean(self):
        data = super().clean()
        if (
            self.instance.status == Deal.OPEN
            and data.get("probability") == Deal.HIGH
            and not data.get("decision_expected_on")
        ):
            self.add_error(
                "decision_expected_on",
                _("This field is required when probability is high."),
            )
        return data

    def save(self):
        instance = super().save(commit=False)
        values = {}

        for vt in ValueType.objects.all():
            key = f"value_{vt.id}"
            if self.cleaned_data.get(key) is not None:
                values[vt] = self.cleaned_data[key]

        instance.value = sum(values.values(), Z2)
        instance.save(skip_value_calculation=True)

        instance.values.exclude(type__in=values.keys()).delete()
        for vt, value in values.items():
            instance.values.update_or_create(type=vt, defaults={"value": value})

        attributes = []
        for group in AttributeGroup.objects.all():
            key = f"attribute_{group.id}"

            if self.cleaned_data.get(key) is not None:
                attributes.append(self.cleaned_data.get(key))

        instance.attributes.set(attributes)
        self.save_m2m()

        to_delete = []
        for user in User.objects.all():
            name = f"user_{user.id}_contribution"
            weight = self.cleaned_data.get(name) or 0
            if weight:
                instance.contributions.update_or_create(
                    user=user, defaults={"weight": weight}
                )
            else:
                to_delete.append(user.id)
        if to_delete:
            instance.contributions.filter(user__in=to_delete).delete()

        return instance


class ContributionSelect(forms.RadioSelect):
    template_name = "deals/contribution_select.html"


class SetStatusForm(ModelForm):
    class Meta:
        model = Deal
        fields = ["status", "closed_on", "closing_type", "closing_notice"]
        widgets = {
            "status": forms.RadioSelect,
            "closing_type": forms.RadioSelect,
            "closing_notice": Textarea,
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs["instance"]
        instance.status = int(kwargs["request"].GET.get("status", instance.status))
        if instance.status in {Deal.ACCEPTED, Deal.DECLINED}:
            instance.closed_on = dt.date.today()
        elif instance.status in {Deal.OPEN}:
            instance.closed_on = None
            instance.closing_type = None
            instance.closing_notice = ""

        super().__init__(*args, **kwargs)
        self.fields["status"].disabled = True

        if instance.status == Deal.OPEN:
            self.fields.pop("closed_on")
            self.fields.pop("closing_type")
            self.fields.pop("closing_notice")

        elif instance.status == Deal.ACCEPTED:
            self.fields["closed_on"].required = True
            self.fields["closing_type"].empty_label = None
            self.fields["closing_type"].label = _("Award of contract")
            self.fields["closing_type"].required = True
            self.fields["closing_type"].queryset = self.fields[
                "closing_type"
            ].queryset.filter(represents_a_win=True)

        elif instance.status == Deal.DECLINED:
            self.fields["closed_on"].required = True
            self.fields["closing_type"].empty_label = None
            self.fields["closing_type"].label = _("Reason for losing")
            self.fields["closing_type"].required = True
            self.fields["closing_type"].queryset = self.fields[
                "closing_type"
            ].queryset.filter(represents_a_win=False)

        else:
            raise Http404

        if instance.status != Deal.OPEN:
            related_offers = instance.related_offers.select_related(
                "owned_by", "project"
            )
            if related_offers:
                self.fields["related_offers"] = forms.ModelMultipleChoiceField(
                    queryset=related_offers,
                    label=_("Accept offers")
                    if instance.status == Deal.ACCEPTED
                    else _("Decline offers"),
                    required=False,
                    widget=forms.CheckboxSelectMultiple,
                    initial=[
                        offer.id
                        for offer in related_offers
                        if offer.status < offer.ACCEPTED
                    ],
                )
                self.fields["related_offers"].choices = [
                    (
                        offer.id,
                        format_html("{}<br>{}", offer.__html__(), offer.status_badge),
                    )
                    for offer in related_offers
                ]

    def clean(self):
        data = super().clean()
        if data["status"] != Deal.OPEN and not data.get("closing_type"):
            self.add_error(
                "closing_type", _("This field is required when closing a deal.")
            )
        if data.get("status") in {Deal.ACCEPTED, Deal.DECLINED}:
            self.offers_to_update = data.get("related_offers", ())
            for offer in self.offers_to_update:
                offer.status = (
                    offer.ACCEPTED
                    if data.get("status") == Deal.ACCEPTED
                    else offer.DECLINED
                )
                try:
                    offer.full_clean()
                except ValidationError as exc:
                    self.add_error(
                        "__all__",
                        _(
                            'Setting the status of offer "%(offer)s" to "%(status)s" is'
                            " not possible because of the following errors: %(error)s"
                        )
                        % {
                            "offer": offer,
                            "status": offer.get_status_display(),
                            "error": " ".join(str(e) for e in exc.messages),
                        },
                    )
        return data

    def save(self, *args, **kwargs):
        instance = super().save(commit=False)
        assert instance.status in {Deal.OPEN, Deal.ACCEPTED, Deal.DECLINED}

        if instance.status in {Deal.ACCEPTED, Deal.DECLINED}:
            projects = set()
            for offer in self.offers_to_update:
                offer.save()
                projects.add(offer.project)

            for project in projects:
                project.solely_declined_offers_warning(request=self.request)

        instance.save()
        return instance
