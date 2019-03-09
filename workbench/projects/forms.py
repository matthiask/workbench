from collections import OrderedDict
from datetime import date

from django import forms, http
from django.forms.models import inlineformset_factory
from django.utils.translation import ugettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service, Effort, Cost
from workbench.tools.forms import ModelForm, Textarea, Picker


class ProjectSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(
            ("", _("All states")),
            ("open", _("Open")),
            ("closed", _("Closed")),
            # (_("Exact"), Project.STATUS_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )
    type = forms.ChoiceField(
        choices=[("", _("All types"))] + Project.TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )
    owned_by = forms.TypedChoiceField(
        label=_("owned by"),
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = [
            ("", _("All users")),
            (0, _("Owned by inactive users")),
            (
                _("Active"),
                [
                    (u.id, u.get_full_name())
                    for u in User.objects.filter(is_active=True)
                ],
            ),
        ]

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s") == "open":
            queryset = queryset.filter(closed_on__isnull=True)
        elif data.get("s") == "closed":
            queryset = queryset.filter(closed_on__isnull=False)
        if data.get("type"):
            queryset = queryset.filter(type=data.get("type"))
        if data.get("owned_by") == 0:
            queryset = queryset.filter(owned_by__is_active=False)
        elif data.get("owned_by"):
            queryset = queryset.filter(owned_by=data.get("owned_by"))

        return queryset.select_related("customer", "contact__organization", "owned_by")

    def response(self, request, queryset):
        if "s" not in request.GET:
            return http.HttpResponseRedirect("?s=open")


class ProjectForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Project
        fields = ("customer", "contact", "title", "description", "owned_by", "type")
        widgets = {
            "customer": Picker(model=Organization),
            "contact": Picker(model=Person),
            "description": Textarea,
            "type": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].choices = Project.TYPE_CHOICES
        if self.instance.pk:
            self.fields["is_closed"] = forms.BooleanField(
                label=_("is closed"),
                required=False,
                initial=bool(self.instance.closed_on),
            )

    def save(self):
        instance = super().save(commit=False)
        if not instance.closed_on and self.cleaned_data.get("is_closed"):
            instance.closed_on = date.today()
        if instance.closed_on and not self.cleaned_data.get("is_closed"):
            instance.closed_on = None
        instance.save()
        return instance


class ServiceForm(ModelForm):
    class Meta:
        model = Service
        fields = ["offer", "title", "description"]
        widgets = {"description": Textarea()}

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if not self.project:
            self.project = kwargs["instance"].project

        offer = kwargs["request"].GET.get("offer")
        if offer:
            kwargs.setdefault("initial", {}).setdefault("offer", offer)

        super().__init__(*args, **kwargs)

        kwargs.pop("request")
        # This makes saving formsets for just created services work:
        kwargs["instance"] = self.instance
        self.formsets = OrderedDict(
            (
                ("efforts", EffortFormset(*args, **kwargs)),
                ("costs", CostFormset(*args, **kwargs)),
            )
        )

        if self.project:
            self.fields["offer"].queryset = self.project.offers.all()
        else:
            self.fields["offer"].queryset = Offer.objects.none()

    def is_valid(self):
        return all(
            [super().is_valid()]
            + [formset.is_valid() for formset in self.formsets.values()]
        )

    def save(self):
        instance = super().save(commit=False)
        instance.project = self.project
        if not instance.pk:
            instance.save()
        for formset in self.formsets.values():
            formset.save()
        instance.save()
        return instance


EffortFormset = inlineformset_factory(
    Service,
    Effort,
    fields=("title", "billing_per_hour", "hours", "service_type"),
    extra=0,
    widgets={
        "service_type": forms.Select(attrs={"class": "custom-select"}),
        "hours": forms.NumberInput(
            attrs={"class": "form-control short", "placeholder": _("hours")}
        ),
    },
)

CostFormset = inlineformset_factory(
    Service,
    Cost,
    fields=("title", "cost", "third_party_costs"),
    extra=0,
    widgets={
        "title": forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("title")}
        ),
        "cost": forms.NumberInput(
            attrs={"class": "form-control short", "placeholder": _("cost")}
        ),
        "third_party_costs": forms.NumberInput(
            attrs={"class": "form-control", "placeholder": _("third party costs")}
        ),
    },
)


class DeleteServiceForm(ModelForm):
    class Meta:
        model = Service
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.loggedhours.exists() or self.instance.loggedcosts.exists():
            self.fields["merge_into"] = forms.ModelChoiceField(
                queryset=self.instance.project.services.exclude(pk=self.instance.pk),
                label=_("Merge log into"),
            )

    def save(self):
        into = self.cleaned_data["merge_into"]
        self.instance.loggedhours.update(service=into)
        self.instance.loggedcosts.update(service=into)
        self.instance.delete()
        return into
