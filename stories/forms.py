import itertools

from django import forms
from django.utils.translation import ugettext_lazy as _

from stories.models import Story, RenderedService
from tools.forms import ModelForm


class RenderedServiceForm(ModelForm):
    user_fields = ('rendered_by',)
    default_to_current_user = user_fields

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
        Story.objects.all(),
        label=_('Merge into'),
    )

    def __init__(self, *args, **kwargs):
        self.story = kwargs.pop('instance')
        super().__init__(*args, **kwargs)

        stories = self.story.project.stories.exclude(pk=self.story.pk)
        self.fields['merge_into'].choices = [('', '----------')] + [
            (str(key), [(story.id, story) for story in group])
            for key, group
            in itertools.groupby(stories, key=lambda story: story.release)
        ]

    def save(self):
        merge_into = self.cleaned_data['merge_into']
        self.story.merge_into(merge_into)
        return merge_into
