import datetime as dt

from django import forms
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
            "status",
        )
        widgets = {
            "customer": Autocomplete(model=Organization),
            "contact": Autocomplete(model=Person),
            "description": Textarea,
            "status": forms.RadioSelect,
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

        if self.instance.id:
            attributes = {a.group_id: a.id for a in self.instance.attributes.all()}
        else:
            attributes = {}
        for group in AttributeGroup.objects.active():
            key = "attribute_{}".format(group.id)
            self.fields[key] = forms.ModelChoiceField(
                queryset=group.values.active(),
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

        attributes = []
        for group in AttributeGroup.objects.active():
            key = "attribute_{}".format(group.id)

            if self.cleaned_data.get(key) is not None:
                attributes.append(self.cleaned_data.get(key))

        instance.attributes.set(attributes)

        if instance.status in {instance.OPEN} and instance.closed_on:
            instance.closed_on = None
        elif (
            instance.status in {instance.ACCEPTED, instance.DECLINED}
            and not instance.closed_on
        ):
            instance.closed_on = dt.date.today()

        instance.save()
        return instance
