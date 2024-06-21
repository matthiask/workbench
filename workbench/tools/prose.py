from django_prose_editor.fields import ProseEditorField


class RestrictedProseField(ProseEditorField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "config", {"types": ["heading", "strong", "em", "sub", "sup", "hard_break"]}
        )
        super().__init__(*args, **kwargs)
