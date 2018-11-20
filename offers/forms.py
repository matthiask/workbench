from collections import OrderedDict
from decimal import Decimal

from django import forms
from django.forms.models import inlineformset_factory
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from contacts.forms import PostalAddressSelectionForm
from offers.models import Offer, Service, Effort, Cost
from tools.formats import local_date_format
from tools.forms import ModelForm, Textarea, WarningsForm


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


class ServiceForm(ModelForm):
    class Meta:
        model = Service
        fields = ("title", "description")
        widgets = {"description": Textarea()}

    def __init__(self, *args, **kwargs):
        self.offer = kwargs.pop("offer", None)
        super().__init__(*args, **kwargs)
        kwargs.pop("request")
        self.formsets = (
            OrderedDict(
                (
                    ("efforts", EffortFormset(*args, **kwargs)),
                    ("costs", CostFormset(*args, **kwargs)),
                )
            )
            if self.instance.pk
            else OrderedDict()
        )

        if self.offer:
            self.instance.offer = self.offer

    def is_valid(self):
        return all(
            [super().is_valid()]
            + [formset.is_valid() for formset in self.formsets.values()]
        )

    def save(self):
        instance = super().save(commit=False)
        for formset in self.formsets.values():
            formset.save()

        efforts = instance.efforts.all()
        instance.effort_hours = sum((e.hours for e in efforts), Decimal())
        instance.cost += sum((e.cost for e in efforts), Decimal())
        instance.cost += sum((c.cost for c in instance.costs.all()), Decimal())
        instance.save()
        return instance


EffortFormset = inlineformset_factory(
    Service, Effort, fields=("service_type", "hours"), extra=0
)

CostFormset = inlineformset_factory(Service, Cost, fields=("title", "cost"), extra=0)
