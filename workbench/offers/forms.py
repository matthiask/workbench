from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from workbench.contacts.forms import PostalAddressSelectionForm
from workbench.offers.models import Offer
from workbench.projects.models import Service
from workbench.tools.formats import local_date_format
from workbench.tools.forms import ModelForm, WarningsForm


class OfferSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(("", _("All states")),) + Offer.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s"):
            queryset = queryset.filter(status=data.get("s"))

        return queryset


class CreateOfferForm(PostalAddressSelectionForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Offer
        fields = ("title", "description", "owned_by")

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        kwargs["initial"] = {
            "title": self.project.title,
            "description": self.project.description,
        }

        super().__init__(*args, **kwargs)

        self.instance.project = self.project
        self.add_postal_address_selection(
            organization=self.project.customer, person=self.project.contact
        )


class OfferForm(WarningsForm, ModelForm):
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
        widgets = {"status": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
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

    def clean(self):
        data = super().clean()
        s_dict = dict(Offer.STATUS_CHOICES)

        if data.get("status", 0) >= Offer.ACCEPTED:
            if not self.instance.closed_at:
                self.instance.closed_at = timezone.now()

        if self.instance.closed_at and data.get("status", 99) < Offer.ACCEPTED:
            if self.request.POST.get("ignore_warnings"):
                self.instance.closed_at = None
            else:
                self.add_warning(
                    _(
                        "You are attempting to set status to '%(to)s',"
                        " but the offer has already been closed on %(closed)s."
                        " Are you sure?"
                    )
                    % {
                        "to": s_dict[data["status"]],
                        "closed": local_date_format(self.instance.closed_at, "d.m.Y"),
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
