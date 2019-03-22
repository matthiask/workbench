from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.activities.models import Activity
from workbench.contacts.models import Person
from workbench.deals.models import Deal
from workbench.projects.models import Project
from workbench.tools.forms import ModelForm, Textarea


class ActivitySearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=[("", _("Open")), ("all", _("All"))],
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
        if data.get("s") != "all":
            queryset = queryset.filter(completed_at__isnull=True)
        if data.get("owned_by") == 0:
            queryset = queryset.filter(owned_by__is_active=False)
        elif data.get("owned_by"):
            queryset = queryset.filter(owned_by=data.get("owned_by"))

        return queryset.select_related(
            "project", "deal", "contact__organization", "owned_by"
        )


class ActivityForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Activity
        fields = ["title", "notes", "owned_by", "due_on"]
        widgets = {"notes": Textarea}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["is_completed"] = forms.BooleanField(
                label=_("is completed"),
                required=False,
                initial=bool(self.instance.completed_at),
            )

    def save(self):
        instance = super().save(commit=False)
        if not instance.completed_at and self.cleaned_data.get("is_completed"):
            instance.completed_at = timezone.now()
        if instance.completed_at and not self.cleaned_data.get("is_completed"):
            instance.completed_at = None

        for model, field in [(Project, "project"), (Person, "contact"), (Deal, "deal")]:
            try:
                pk = self.request.GET.get(field)
                if pk is None:
                    continue

                setattr(instance, field, model._default_manager.get(pk=pk))
            except (model.DoesNotExist, TypeError, ValueError):
                pass

        instance.save()
        return instance
