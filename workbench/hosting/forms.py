from django import forms
from django.utils.translation import gettext_lazy as _

from workbench.contacts.models import Organization, Person
from workbench.hosting.models import Server, Site, SiteContact
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea, add_prefix


class SiteSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search")}
        ),
        label="",
    )
    s = forms.ChoiceField(
        choices=[
            ("", _("Active")),
            ("problems", _("With problems")),
            ("archived", _("Archived")),
            ("all", _("All")),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    server = forms.ModelChoiceField(
        queryset=Server.objects.all(),
        required=False,
        empty_label=_("All servers"),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    org = forms.ModelChoiceField(
        queryset=Organization.objects.all(),
        required=False,
        widget=Autocomplete(model=Organization),
        label="",
    )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.search(data.get("q") or "")
        if data.get("s") == "problems":
            queryset = queryset.with_problems()
        elif data.get("s") == "archived":
            queryset = queryset.filter(is_archived=True)
        elif data.get("s") != "all":
            queryset = queryset.active()
        queryset = self.apply_renamed(queryset, "server", "server")
        queryset = self.apply_renamed(queryset, "org", "customer")
        return (
            queryset
            .with_problem_flags()
            .select_related("server", "customer", "owned_by")
            .prefetch_related("contacts__person")
        )


class ServerSearchForm(Form):
    s = forms.ChoiceField(
        choices=[("", _("Active")), ("archived", _("Archived")), ("all", _("All"))],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def filter(self, queryset):
        if self.cleaned_data.get("s") == "archived":
            return queryset.filter(is_archived=True)
        if self.cleaned_data.get("s") != "all":
            return queryset.filter(is_archived=False)
        return queryset


@add_prefix("modal")
class ServerForm(ModelForm):
    class Meta:
        model = Server
        fields = ["title", "notes", "is_archived"]
        widgets = {"notes": Textarea}


class SiteForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Site
        fields = [
            "title",
            "domains",
            "server",
            "customer",
            "owned_by",
            "password_manager_url",
            "no_invoice_reason",
            "notes",
            "is_archived",
        ]
        widgets = {
            "customer": Autocomplete(model=Organization),
            "domains": Textarea({"rows": 2}),
            "notes": Textarea,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["server"].queryset = Server.objects.filter(
            is_archived=False
        ) | Server.objects.filter(pk=self.instance.server_id)
        if not self.instance.pk:
            self.fields.pop("is_archived")
            for field in ["customer", "server"]:
                if value := self.request.GET.get(field):
                    self.initial.setdefault(field, value)

    def clean_title(self):
        return self.cleaned_data["title"].strip().lower()

    def clean_domains(self):
        return "\n".join(
            name.strip().lower()
            for name in self.cleaned_data["domains"].splitlines()
            if name.strip()
        )


@add_prefix("modal")
class SiteContactForm(ModelForm):
    class Meta:
        model = SiteContact
        fields = ["person", "role"]
        widgets = {
            "person": Autocomplete(model=Person),
            "role": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        self.site = kwargs.pop("site", None) or kwargs["instance"].site
        super().__init__(*args, **kwargs)
        self.instance.site = self.site
        self.fields["role"].choices = SiteContact.ROLE_CHOICES
        if not self.instance.pk:
            self.initial.setdefault("role", SiteContact.OUTAGE)

    def clean(self):
        data = super().clean()
        if (
            data.get("person")
            and data.get("role")
            and SiteContact.objects
            .filter(site=self.site, person=data["person"], role=data["role"])
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError(
                _("This person is already a contact of the site with this role.")
            )
        return data
