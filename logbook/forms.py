from decimal import Decimal, ROUND_UP

from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from accounts.models import User
from logbook.models import LoggedHours, LoggedCost
from tools.forms import ModelForm, Textarea


class LoggedHoursSearchForm(forms.Form):
    rendered_by = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label=_('rendered by'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def filter(self, queryset):
        data = self.cleaned_data
        if data.get('rendered_by'):
            queryset = queryset.filter(rendered_by=data.get('rendered_by'))

        return queryset


class LoggedHoursForm(ModelForm):
    user_fields = default_to_current_user = ('rendered_by',)

    class Meta:
        model = LoggedHours
        fields = ('task', 'rendered_by', 'rendered_on', 'hours', 'description')
        widgets = {
            'description': Textarea(),
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        if self.project:
            initial = kwargs.setdefault('initial', {})
            request = kwargs['request']

            if request.GET.get('task'):
                initial['task'] = request.GET.get('task')

            latest = LoggedHours.objects.filter(
                rendered_by=kwargs['request'].user,
            ).order_by('-created_at').first()
            if latest and (timezone.now() - latest.created_at).seconds < 7200:
                seconds = (timezone.now() - latest.created_at).seconds
                initial.setdefault(
                    'hours',
                    (seconds / Decimal(3600)).quantize(
                        Decimal('0.0'), rounding=ROUND_UP),
                )
        else:
            self.project = kwargs['instance'].task.project

        super().__init__(*args, **kwargs)
        self.fields['task'].choices = [('', '----------')] + [(
            task.id,
            task.__html__(),
        ) for task in self.project.tasks.all()]

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
        instance.save()
        return instance


class LoggedCostForm(ModelForm):
    class Meta:
        model = LoggedCost
        fields = ('service', 'rendered_on', 'cost', 'description')
        widgets = {
            'description': Textarea(),
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        if not self.project:
            self.project = self.instance.project
        self.fields['service'].queryset =\
            self.fields['service'].queryset.filter(
                offer__project=self.project,
            )

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.project = self.project
            instance.created_by = self.request.user
        instance.save()
        return instance
