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


"""
class EffortForm(forms.Form):
    effort_field = None

    class Meta:
        model = Project
        fields = ()

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('instance')
        self.request = kwargs.pop('request')

        super().__init__(*args, **kwargs)

        self.requiredservices = defaultdict(dict)
        for o in RequiredService.objects.filter(story__project=self.project):
            self.requiredservices[o.story_id][o.service_type_id] = o

        self.servicetypes = list(ServiceType.objects.all())
        self.stories = []

        for story in self.project.stories.all():
            row = {
                'story': story,
                'servicetypes': [],
            }
            for type in self.servicetypes:
                try:
                    rs = self.requiredservices[story.id][type.id]
                    value = getattr(rs, self.effort_field)
                except KeyError:
                    rs = None
                    value = None

                field = forms.DecimalField(
                    label=type.title,
                    max_digits=5,
                    decimal_places=2,
                    required=False,
                    initial=value)
                key = 'e_%s_%s' % (story.id, type.id)
                self.fields[key] = field
                row['servicetypes'].append({
                    'field': self[key],
                    'instance': rs,
                })

            self.stories.append(row)

    def save(self):
        RequiredService.objects.filter(story__project=self.project).update(**{
            self.effort_field: 0,
        })

        for story in self.project.stories.all():
            for type in self.servicetypes:
                value = self.cleaned_data.get('e_%s_%s' % (story.id, type.id))
                if value is not None:
                    try:
                        rs = self.requiredservices[story.id][type.id]
                    except KeyError:
                        rs = RequiredService(
                            story=story,
                            service_type=type,
                            offered_effort=value,
                            planning_effort=value,
                        )

                    setattr(rs, self.effort_field, value)
                    rs.save()

        return self.project


class EstimationForm(EffortForm):
    effort_field = 'offered_effort'
"""


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
        self.task = kwargs.pop('task')
        super().__init__(*args, **kwargs)

    def save(self):
        instance = super().save(commit=False)
        instance.created_by = self.request.user
        instance.task = self.task
        instance.save()
        return instance
