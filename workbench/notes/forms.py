from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _

from workbench.notes.models import Note
from workbench.tools.forms import ModelForm, Textarea


class NoteForm(ModelForm):
    class Meta:
        model = Note
        fields = ["title", "description"]
        widgets = {"description": Textarea}

    def __init__(self, *args, **kwargs):
        content_object = kwargs.pop("content_object", None)
        super().__init__(*args, **kwargs)

        self.fields["content_type"] = forms.ModelChoiceField(
            ContentType.objects.all(),
            initial=ContentType.objects.get_for_model(content_object)
            if content_object
            else None,
            widget=forms.HiddenInput,
        )
        self.fields["object_id"] = forms.IntegerField(
            initial=content_object.pk if content_object else None,
            widget=forms.HiddenInput,
        )

    def clean(self):
        data = super().clean()
        try:
            data["content_object"] = data["content_type"].get_object_for_this_type(
                pk=data["object_id"]
            )
        except (KeyError, ObjectDoesNotExist):
            self.add_error(
                "__all__",
                _("Unable to determine the object this note should be added to."),
            )
        return data

    def save(self):
        instance = super().save(commit=False)
        instance.content_object = self.cleaned_data["content_object"]
        instance.created_by = self.request.user
        instance.save()
        return instance
