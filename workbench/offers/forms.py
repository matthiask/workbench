from django import forms
from django.contrib import messages
from django.db.models import Q
from django.forms.models import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.forms import PostalAddressSelectionForm
from workbench.contacts.models import Organization
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service
from workbench.tools.formats import local_date_format
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea, add_prefix
from workbench.tools.models import ProtectedError, SlowCollector


class OfferSearchForm(Form):
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
            (_("Exact"), Offer.STATUS_CHOICES),
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
        if data.get("s") == "all":
            pass
        elif data.get("s"):
            queryset = queryset.filter(status=data.get("s"))
        else:
            queryset = queryset.filter(status__lte=Offer.OFFERED)
        queryset = self.apply_renamed(queryset, "org", "project__customer")
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related(
            "owned_by",
            "project__owned_by",
            "project__customer",
            "project__contact__organization",
        )


def warn_if_not_in_preparation(form):
    if (
        form.instance.pk
        and form.instance.status >= form.instance.OFFERED
        and form.request.method == "GET"
    ):
        messages.warning(
            form.request,
            _(
                "This offer is not in preparation anymore."
                " I assume you know what you're doing and wont stand in the way."
            ),
        )


class OfferForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Offer
        fields = (
            "offered_on",
            "valid_until",
            "title",
            "description",
            "owned_by",
            "status",
            "postal_address",
            "subtotal",
            "discount",
            "liable_to_vat",
            "show_service_details",
        )
        widgets = {
            "description": Textarea,
            "status": forms.RadioSelect,
            "postal_address": Textarea,
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:  # Creating a new offer
            kwargs.setdefault("initial", {}).update({"title": self.project.title})
        else:
            self.project = kwargs["instance"].project

        super().__init__(*args, **kwargs)
        warn_if_not_in_preparation(self)

        self.instance.project = self.project
        self.service_candidates = Service.objects.filter(
            Q(project=self.project), Q(offer__isnull=True) | Q(offer=self.instance)
        )

        self.fields["services"] = forms.ModelMultipleChoiceField(
            queryset=self.service_candidates,
            label=_("services"),
            widget=forms.CheckboxSelectMultiple,
            required=False,
            initial=(
                self.instance.services.values_list("pk", flat=True)
                if self.instance.pk
                else self.service_candidates.values_list("pk", flat=True)
            ),
        )

        self.order_fields(
            field
            for field in list(self.fields)
            if field
            not in {"subtotal", "discount", "liable_to_vat", "show_service_details"}
        )

        self.add_postal_address_selection_if_empty(
            person=self.project.contact, organization=self.project.customer
        )
        self.fields["subtotal"].disabled = True

    def clean(self):
        data = super().clean()
        s_dict = dict(Offer.STATUS_CHOICES)

        if self.instance.closed_on and data["status"] < Offer.ACCEPTED:
            self.add_warning(
                _(
                    "You are attempting to set status to '%(to)s',"
                    " but the offer has already been closed on %(closed)s."
                    " Are you sure?"
                )
                % {
                    "to": s_dict[data["status"]],
                    "closed": local_date_format(self.instance.closed_on),
                },
                code="status-change-but-already-closed",
            )

        if data["status"] == Offer.DECLINED:
            self.add_warning(
                _(
                    "You are setting the offer status to 'Declined'."
                    " However, if you just want to change a few things"
                    " and send the offer to the client again then you"
                    " could just as well put the offer back into preparation."
                ),
                code="yes-please-decline",
            )

        return data

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.save()
        self.cleaned_data["services"].update(offer=instance)
        self.service_candidates.exclude(id__in=self.cleaned_data["services"]).update(
            offer=None
        )
        instance.save()
        instance.project.solely_declined_offers_warning(request=self.request)
        return instance


class OfferPricingForm(ModelForm):
    class Meta:
        model = Offer
        fields = ("subtotal", "discount", "total_excl_tax", "liable_to_vat", "total")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        warn_if_not_in_preparation(self)

        self.fields["subtotal"].disabled = True
        self.fields["total_excl_tax"].disabled = True
        self.fields["total"].disabled = True

        kwargs.pop("request")
        self.formsets = (
            {"services": ServiceFormset(*args, **kwargs)} if self.instance.pk else {}
        )

    def is_valid(self):
        return all(
            [super().is_valid()]
            + [formset.is_valid() for formset in self.formsets.values()]
        )

    def save(self, commit=True):
        for formset in self.formsets.values():
            formset.save()
        return super().save()


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.project.flat_rate is not None:
            self.fields["effort_type"].disabled = True
            self.fields["effort_rate"].disabled = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.save(skip_related_model=True)
        return instance


ServiceFormset = inlineformset_factory(
    Offer,
    Service,
    form=ServiceForm,
    fields=("title", "effort_type", "effort_rate", "effort_hours", "cost"),
    extra=0,
    can_delete=False,
)


@add_prefix("modal")
class OfferCopyForm(Form):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        widget=Autocomplete(model=Project, params={"only_open": "on"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        super().__init__(*args, **kwargs)

    def clean_project(self):
        project = self.cleaned_data.get("project")
        if project == self.project:
            self.add_warning(
                _("Same project selected as offer already belongs to."),
                code="same-project",
            )
        return project


class OfferDeleteForm(ModelForm):
    class Meta:
        model = Offer
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        collector = SlowCollector(using=self.instance._state.db)
        try:
            collector.collect(self.instance.services.all())
        except ProtectedError:
            pass
        else:
            self.fields["delete_services"] = forms.BooleanField(
                label=_("Delete offers' services?"), required=False
            )

    def delete(self):
        if self.cleaned_data.get("delete_services"):
            self.instance.services.all().delete()
        self.instance.delete()


@add_prefix("modal")
class OfferAutocompleteForm(forms.Form):
    offer = forms.ModelChoiceField(
        queryset=Offer.objects.all(),
        widget=Autocomplete(model=Offer),
        label="",
    )
