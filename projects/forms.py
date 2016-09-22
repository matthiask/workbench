from django import forms
from django.utils.translation import ugettext_lazy as _

from contacts.models import Organization, Person
from projects.models import Project, Task, Comment
from offers.models import Service
from tools.forms import ModelForm, Picker, Textarea


class ProjectSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(('', _('All states')),) + Project.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def filter(self, queryset):
        if not self.is_valid():
            return queryset

        data = self.cleaned_data
        if data.get('s'):
            queryset = queryset.filter(status=data.get('s'))

        return queryset


class ProjectForm(ModelForm):
    user_fields = default_to_current_user = ('owned_by',)

    class Meta:
        model = Project
        fields = (
            'customer', 'contact', 'title', 'description', 'owned_by',
            'status', 'invoicing', 'maintenance')
        widgets = {
            'customer': Picker(model=Organization),
            'contact': Picker(model=Person),
            'status': forms.RadioSelect,
        }


class ApprovedHoursForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('instance')
        self.request = kwargs.pop('request')

        super().__init__(*args, **kwargs)

        for service in Service.objects.filter(offer__project=self.project):
            self.fields['service_%s_approved_hours' % service.id] =\
                forms.DecimalField(
                    label='%s (%.1fh)' % (
                        service,
                        service.effort_hours,
                    ),
                    required=False,
                    max_digits=5,
                    decimal_places=2,
                    initial=service._approved_hours,
                )

    def save(self):
        for service in Service.objects.filter(offer__project=self.project):
            service._approved_hours = self.cleaned_data.get(
                'service_%s_approved_hours' % service.id)
            service.save()
        return self.project


class TaskForm(ModelForm):
    user_fields = ('owned_by',)

    class Meta:
        model = Task
        fields = (
            'title',
            'description',
            'type',
            'priority',
            'owned_by',
            'status',
            'due_on',
            'service',
        )
        widgets = {
            'type': forms.RadioSelect,
            'priority': forms.RadioSelect,
            'status': forms.RadioSelect,
            'description': Textarea(),
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(
            offer__project=self.project or self.instance.project,
        )

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
            instance.project = self.project
        instance.save()
        return instance


class CommentForm(ModelForm):
    class Meta:
        model = Comment
        fields = ('notes',)
        widgets = {
            'notes': Textarea(),
        }

    def __init__(self, *args, **kwargs):
        self.task = kwargs.pop('task', None)
        super().__init__(*args, **kwargs)

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
            instance.task = self.task
        instance.save()
        return instance
