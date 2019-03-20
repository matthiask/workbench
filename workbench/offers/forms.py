from datetime import date

from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from workbench.contacts.forms import PostalAddressSelectionForm
from workbench.offers.models import Offer
from workbench.projects.models import Service
from workbench.tools.formats import local_date_format
from workbench.tools.forms import Textarea, WarningsForm


class OfferSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(
            ("all", _("All states")),
            ("", _("Open")),
            (_("Exact"), Offer.STATUS_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s") == "all":
            pass
        elif data.get("s") == "":
            queryset = queryset.filter(status__lte=Offer.OFFERED)
        elif data.get("s"):
            queryset = queryset.filter(status=data.get("s"))

        return queryset.select_related(
            "project__owned_by", "project__customer", "project__contact__organization"
        )


class CreateOfferForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Offer
        fields = ("title", "description", "owned_by", "postal_address")

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        kwargs["initial"] = {
            "title": self.project.title,
            "description": self.project.description,
        }

        super().__init__(*args, **kwargs)

        self.instance.project = self.project
        self.add_postal_address_selection(
            person=self.project.contact, organization=self.project.customer
        )

        self.service_candidates = Service.objects.filter(
            Q(project=self.instance.project), Q(offer__isnull=True)
        )

        self.fields["services"] = forms.ModelMultipleChoiceField(
            queryset=self.service_candidates,
            label=_("services"),
            widget=forms.CheckboxSelectMultiple,
            required=False,
            initial=self.service_candidates.values_list("pk", flat=True),
        )

    def save(self):
        instance = super().save()
        self.cleaned_data["services"].update(offer=instance)
        instance.save()
        return instance


class OfferForm(WarningsForm, PostalAddressSelectionForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Offer
        fields = (
            "offered_on",
            "title",
            "description",
            "owned_by",
            "status",
            "postal_address",
            "liable_to_vat",
        )
        widgets = {
            "description": Textarea,
            "status": forms.RadioSelect,
            "postal_address": Textarea,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_candidates = Service.objects.filter(
            Q(project=self.instance.project),
            Q(offer__isnull=True) | Q(offer=self.instance),
        )

        self.fields["services"] = forms.ModelMultipleChoiceField(
            queryset=self.service_candidates,
            label=_("services"),
            widget=forms.CheckboxSelectMultiple,
            required=False,
            initial=self.instance.services.values_list("pk", flat=True),
        )

        if not self.instance.postal_address:
            project = self.instance.project
            self.add_postal_address_selection(
                person=project.contact, organization=project.organization
            )

    def clean(self):
        data = super().clean()
        s_dict = dict(Offer.STATUS_CHOICES)

        if data.get("status", 0) >= Offer.ACCEPTED:
            if not self.instance.closed_on:
                self.instance.closed_on = date.today()

        if self.instance.closed_on and data.get("status", 99) < Offer.ACCEPTED:
            if self.should_ignore_warnings():
                self.instance.closed_on = None
            else:
                self.add_warning(
                    _(
                        "You are attempting to set status to '%(to)s',"
                        " but the offer has already been closed on %(closed)s."
                        " Are you sure?"
                    )
                    % {
                        "to": s_dict[data["status"]],
                        "closed": local_date_format(self.instance.closed_on, "d.m.Y"),
                    }
                )

        return data

    def save(self):
        instance = super().save(commit=False)
        if instance.pk:
            self.cleaned_data["services"].update(offer=instance)
            self.service_candidates.exclude(
                id__in=self.cleaned_data["services"]
            ).update(offer=None)
        instance.save()
        return instance
