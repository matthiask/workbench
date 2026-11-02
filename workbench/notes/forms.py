from authlib.email import render_to_mail
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _, gettext_lazy, override

from workbench.accounts.models import User
from workbench.notes.models import TARGETS, Note, visible_content_types
from workbench.tools.forms import Form, ModelForm, Textarea


class NoteSearchForm(Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": gettext_lazy("Search")}
        ),
        label="",
    )
    type = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    created_by = forms.TypedChoiceField(
        coerce=int,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the notes the user may see, see the notes API
        self.types = visible_content_types(self.request.user)
        self.fields["type"].choices = [("", _("All objects"))] + [
            (key, TARGETS[key][0]._meta.verbose_name_plural.capitalize())
            for key in self.types.values()
        ]
        self.fields["created_by"].choices = User.objects.choices(
            collapse_inactive=False, myself=True
        )

    def filter(self, queryset):
        data = self.cleaned_data
        queryset = queryset.visible(self.types).search(data.get("q"))
        if data.get("type"):
            model = TARGETS[data["type"]][0]
            queryset = queryset.filter(
                content_type=ContentType.objects.get_for_model(model)
            )
        if data.get("created_by") == -1:
            queryset = queryset.filter(created_by=self.request.user)
        elif data.get("created_by"):
            queryset = queryset.filter(created_by=data["created_by"])
        return queryset.select_related(
            "created_by", "content_type"
        ).with_content_objects()


class NoteForm(ModelForm):
    class Meta:
        model = Note
        fields = ["title", "description"]
        widgets = {"description": Textarea({"rows": 15})}

    def __init__(self, *args, **kwargs):
        content_object = kwargs.pop("content_object", None)
        super().__init__(*args, **kwargs)

        self.is_new = not self.instance.pk

        if self.is_new:
            self.fields["content_type"] = forms.ModelChoiceField(
                ContentType.objects.all(),
                initial=ContentType.objects.get_for_model(content_object).pk
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
        if self.is_new:
            try:
                data["content_object"] = data["content_type"].get_object_for_this_type(
                    pk=data["object_id"]
                )
            except KeyError, ObjectDoesNotExist:
                self.add_error(
                    "__all__",
                    _("Unable to determine the object this note should be added to."),
                )
        return data

    def save(self):
        if not self.is_new:
            return super().save()
        instance = super().save(commit=False)
        instance.content_object = self.cleaned_data["content_object"]
        instance.created_by = self.request.user
        instance.save()

        owned_by = getattr(instance.content_object, "owned_by", None)
        if owned_by and owned_by.is_active and owned_by != instance.created_by:
            with override(owned_by.language):
                render_to_mail(
                    "notes/note_notification",
                    {
                        "note": instance,
                        "url": self.request.build_absolute_uri(
                            instance.content_object.get_absolute_url()
                        ),
                    },
                    to=[owned_by.email],
                    reply_to=[owned_by.email, instance.created_by.email],
                ).send(fail_silently=True)

        return instance
