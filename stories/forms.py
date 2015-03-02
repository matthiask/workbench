from django import forms
from django.utils.translation import ugettext_lazy as _

from stories.models import Story, RenderedService
from tools.forms import ModelForm


class RenderedServiceForm(ModelForm):
    user_fields = ('rendered_by',)

    class Meta:
        model = RenderedService
        fields = (
            'rendered_on', 'rendered_by', 'hours', 'description',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class MergeStoryForm(forms.Form):
    merge_into = forms.ModelChoiceField(
        Story,
        label=_('Merge into'),
    )

    def __init__(self, *args, **kwargs):
        self.story = kwargs.pop('story')
        super().__init__(*args, **kwargs)

        stories = self.story.project.stories.exclude(pk=self.story.pk)
        self.fields['merge_into'].queryset = stories
