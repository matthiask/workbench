from django import forms, http
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from contacts.models import Organization, Person
from projects.models import Project, Task, Comment
from offers.models import Service
from tools.forms import ModelForm, Picker, Textarea


class ProjectSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(
            ("", _("All states")),
            ("open", _("Open")),
            (_("Exact"), Project.STATUS_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get("s") == "open":
            queryset = queryset.filter(status__lte=Project.WORK_IN_PROGRESS)
        elif data.get("s"):
            queryset = queryset.filter(status=data.get("s"))

        return queryset

    def response(self, request):
        if "s" not in request.GET:
            return http.HttpResponseRedirect("?s=open")


class ProjectForm(ModelForm):
    user_fields = default_to_current_user = ("owned_by",)

    class Meta:
        model = Project
        fields = (
            "customer",
            "contact",
            "title",
            "description",
            "owned_by",
            "status",
            "invoicing",
            "maintenance",
        )
        widgets = {
            "customer": Picker(model=Organization),
            "contact": Picker(model=Person),
            "status": forms.RadioSelect,
        }


class ApprovedHoursForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("instance")
        self.request = kwargs.pop("request")

        super().__init__(*args, **kwargs)

        for service in Service.objects.filter(offer__project=self.project):
            self.fields["service_%s_approved_hours" % service.id] = forms.DecimalField(
                label=service.title,
                required=False,
                max_digits=5,
                decimal_places=2,
                initial=service._approved_hours,
                help_text=_("The sum of all offered efforts amount to %.1f hours.")
                % (service.effort_hours,),
            )

    def save(self):
        for service in Service.objects.filter(offer__project=self.project):
            service._approved_hours = self.cleaned_data.get(
                "service_%s_approved_hours" % service.id
            )
            service.save()
        return self.project


class TaskSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(
            ("", _("All states")),
            ("open", _("Open")),
            (_("Exact"), Task.STATUS_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    p = forms.ChoiceField(
        choices=(
            ("", _("All priorities")),
            ("high", _("High and higher")),
            (_("Exact"), Task.PRIORITY_CHOICES),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    owned_by = forms.TypedChoiceField(
        label=_("owned by"),
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = [
            ("", _("All users")),
            (-1, _("Owned by nobody")),
            (-2, _("Owned by inactive users")),
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
            queryset = queryset.filter(status__lt=Task.DONE)
        elif data.get("s"):
            queryset = queryset.filter(status=data.get("s"))
        if data.get("p") == "high":
            queryset = queryset.filter(priority__gte=Task.HIGH)
        elif data.get("p"):
            queryset = queryset.filter(priority=data.get("p"))
        if data.get("owned_by") == -1:
            queryset = queryset.filter(owned_by__isnull=True)
        elif data.get("owned_by") == -2:
            queryset = queryset.filter(owned_by__is_active=False)
        elif data.get("owned_by"):
            queryset = queryset.filter(owned_by=data.get("owned_by"))

        return queryset

    def response(self, request):
        if "s" not in request.GET:
            return http.HttpResponseRedirect("?s=open")


class TaskForm(ModelForm):
    user_fields = ("owned_by",)

    class Meta:
        model = Task
        fields = (
            "title",
            "description",
            "type",
            "priority",
            "owned_by",
            "status",
            "due_on",
            "service",
        )
        widgets = {
            "type": forms.RadioSelect,
            "priority": forms.RadioSelect,
            "status": forms.RadioSelect,
            "description": Textarea(),
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.filter(
            offer__project=self.project or self.instance.project
        )

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
            instance.project = self.project

        if instance.status == instance.DONE and not instance.closed_at:
            instance.closed_at = timezone.now()
        elif instance.status != instance.DONE:
            instance.closed_at = None

        instance.save()
        return instance


class CommentForm(ModelForm):
    class Meta:
        model = Comment
        fields = ("notes",)
        widgets = {"notes": Textarea()}

    def __init__(self, *args, **kwargs):
        self.task = kwargs.pop("task", None)
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.created_by = self.request.user
            self.instance.task = self.task
