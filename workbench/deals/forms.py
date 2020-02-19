import datetime as dt

from django import forms
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.deals.models import AttributeGroup, Deal, Stage, Value, ValueType
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea


class DealSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=(
            ("all", _("All states")),
            ("", _("Open")),
            (_("Exact"), Deal.STATUS_CHOICES),
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
        if data.get("s") == "":
            queryset = queryset.filter(status=Deal.OPEN)
        elif data.get("s") != "all":
            queryset = queryset.filter(status=data.get("s"))
        queryset = self.apply_renamed(queryset, "org", "customer")
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related(
            "stage", "owned_by", "customer", "contact__organization"
        )


class DealForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    stage = forms.ModelChoiceField(
        queryset=Stage.objects.all(),
        label=_("stage"),
        empty_label=None,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Deal
        fields = (
            "contact",
            "customer",
            "title",
            "description",
            "stage",
            "owned_by",
        )
        widgets = {
            "customer": Autocomplete(model=Organization),
            "contact": Autocomplete(model=Person),
            "description": Textarea,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        field = Value._meta.get_field("value")
        values = {v.type_id: v.value for v in self.instance.values.all()}
        for vt in ValueType.objects.all():
            key = "value_{}".format(vt.id)

            self.fields[key] = field.formfield(
                label=vt.title, required=False, initial=values.get(vt.id)
            )

        attributes = (
            {a.group_id: a.id for a in self.instance.attributes.all()}
            if self.instance.id
            else {}
        )
        for group in AttributeGroup.objects.active():
            key = "attribute_{}".format(group.id)
            self.fields[key] = forms.ModelChoiceField(
                queryset=group.attributes.active(),
                required=group.is_required,
                label=group.title,
                widget=forms.RadioSelect,
                initial=attributes.get(group.id),
            )

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        types = set()

        for vt in ValueType.objects.all():
            key = "value_{}".format(vt.id)

            if self.cleaned_data.get(key) is not None:
                self.instance.values.update_or_create(
                    type=vt, value=self.cleaned_data[key]
                )
                types.add(vt.id)

        instance.values.exclude(type__in=types).delete()
        instance.save()

        attributes = []
        for group in AttributeGroup.objects.active():
            key = "attribute_{}".format(group.id)

            if self.cleaned_data.get(key) is not None:
                attributes.append(self.cleaned_data.get(key))

        instance.attributes.set(attributes)

        return instance


class SetStatusForm(ModelForm):
    class Meta:
        model = Deal
        fields = ["status", "closing_type", "closing_notice"]
        widgets = {
            "status": forms.RadioSelect,
            "closing_type": forms.RadioSelect,
            "closing_notice": Textarea,
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs["instance"]
        instance.status = int(kwargs["request"].GET.get("status", instance.status))
        super().__init__(*args, **kwargs)

        if instance.status == Deal.OPEN:
            self.fields["status"].disabled = True
            self.fields.pop("closing_type")
            self.fields.pop("closing_notice")

        elif instance.status == Deal.ACCEPTED:
            self.fields["closing_type"].empty_label = None
            self.fields["closing_type"].label = _("Award of contract")
            self.fields["closing_type"].queryset = self.fields[
                "closing_type"
            ].queryset.filter(represents_a_win=True)
            self.fields["status"].disabled = True

        elif instance.status == Deal.DECLINED:
            self.fields["closing_type"].empty_label = None
            self.fields["closing_type"].label = _("Reason for losing")
            self.fields["closing_type"].queryset = self.fields[
                "closing_type"
            ].queryset.filter(represents_a_win=False)
            self.fields["status"].disabled = True

        else:
            raise Http404

    def clean(self):
        data = super().clean()
        if data["status"] != Deal.OPEN and not data.get("closing_type"):
            self.add_error(
                "closing_type", _("This field is required when closing a deal.")
            )
        return data

    def save(self, *args, **kwargs):
        instance = super().save(commit=False)

        if instance.status in {instance.OPEN}:
            instance.closed_on = None
            instance.closing_type = None
            instance.closing_notice = ""
        elif (
            instance.status in {instance.ACCEPTED, instance.DECLINED}
            and not instance.closed_on
        ):
            instance.closed_on = dt.date.today()
        else:
            raise Http404

        instance.save()
        return instance
