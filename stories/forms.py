from django import forms
from django.utils.translation import ugettext_lazy as _

from stories.models import Story, RenderedService
from tools.forms import ModelForm, Textarea


class RenderedServiceForm(ModelForm):
    user_fields = default_to_current_user = ('rendered_by',)

    class Meta:
        model = RenderedService
        fields = (
            'rendered_by', 'rendered_on', 'hours', 'description',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        self.story = kwargs.pop('story')
        super().__init__(*args, **kwargs)

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.created_by = self.request.user
        instance.story = self.story
        instance.save()
        return instance


class StoryForm(ModelForm):
    user_fields = ('owned_by',)

    class Meta:
        model = Story
        fields = ('title', 'description', 'owned_by')
        widgets = {
            'description': Textarea(),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.pk:
            self.project = instance.project

        super().__init__(*args, **kwargs)

    def save(self):
        instance = super().save(commit=False)
        if not instance.pk:
            instance.requested_by = self.request.user
            instance.project = self.project
        instance.save()
        return instance


class MergeStoryForm(forms.Form):
    merge_into = forms.ModelChoiceField(
        Story.objects.all(),
        label=_('Merge into'),
    )

    def __init__(self, *args, **kwargs):
        self.story = kwargs.pop('instance')
        self.request = kwargs.pop('request')

        super().__init__(*args, **kwargs)

        self.fields['merge_into'].queryset =\
            self.story.project.stories.exclude(pk=self.story.pk)

    def save(self):
        merge_into = self.cleaned_data['merge_into']
        self.story.merge_into(merge_into)
        return merge_into
