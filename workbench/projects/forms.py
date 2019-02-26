from collections import OrderedDict
from decimal import Decimal

from django import forms, http
from django.forms.models import inlineformset_factory
from django.utils.translation import ugettext_lazy as _

from workbench.contacts.models import Organization, Person
from workbench.projects.models import Project, Service, Effort, Cost
from workbench.tools.forms import ModelForm, Textarea, Picker


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


class ServiceForm(ModelForm):
    class Meta:
        model = Service
        fields = ("title", "description")
        widgets = {"description": Textarea()}

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
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

        if self.project:
            self.instance.project = self.project

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
