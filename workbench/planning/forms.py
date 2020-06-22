from django import forms

from workbench.accounts.models import User
from workbench.offers.models import Offer
from workbench.planning.models import PlanningRequest
from workbench.projects.models import Project
from workbench.tools.forms import Autocomplete, Form, ModelForm, Textarea


class PlanningRequestSearchForm(Form):
    created_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["created_by"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def filter(self, queryset):
        """
        data = self.cleaned_data
        queryset = queryset.search(data.get("q"))
        if data.get("s") == "all":
            pass
        elif data.get("s"):
            queryset = queryset.filter(status=data.get("s"))
        else:
            queryset = queryset.filter(status__lte=PlanningRequest.OFFERED)
        queryset = self.apply_renamed(queryset, "org", "project__customer")
        """
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related(
            "created_by",
            "project__owned_by",
            "project__customer",
            "project__contact__organization",
        )


class PlanningRequestForm(ModelForm):
    user_fields = default_to_current_user = ("created_by",)

    class Meta:
        model = PlanningRequest
        fields = (
            "project",
            "offer",
            "title",
            "description",
            "requested_hours",
            "earliest_start_on",
            "completion_requested_on",
            "receivers",
        )
        widgets = {
            "project": Autocomplete(model=Project, params={"only_open": "on"}),
            "offer": Autocomplete(model=Offer),
            "description": Textarea,
        }

    def _____init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        if self.project:  # Creating a new offer
            kwargs.setdefault("initial", {}).update({"title": self.project.title})
        else:
            self.project = kwargs["instance"].project

        super().__init__(*args, **kwargs)
        self.instance.project = self.project

    def save(self):
        if self.instance.pk:
            return super().save()

        instance = super().save(commit=False)
        instance.created_by = self.request.user
        instance.save()
        self.save_m2m()
        return instance
