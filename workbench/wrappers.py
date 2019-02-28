from django import forms
from django.template.loader import render_to_string

from fineforms.wrappers import FieldWrapper, html_safe


@html_safe
class BootstrapFieldWrapper(FieldWrapper):
    template_name = "fineforms/field.html"
    label_suffix = ""
    error_css_class = "error"
    required_css_class = "required"

    def __init__(self, field):
        self.field = field

    def __str__(self):
        extra_classes = []
        if not hasattr(self.field.form, "error_css_class") and self.field.errors:
            extra_classes.append(self.error_css_class)
        if (
            not hasattr(self.field.form, "required_css_class")
            and self.field.field.required
        ):
            extra_classes.append(self.required_css_class)

        widget = self.field.field.widget
        extra_label_classes = []
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = widget.attrs.get("class", "") + " form-check-input"
            extra_label_classes.append("form-check-label")
        elif isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
            pass
        else:
            widget.attrs["class"] = widget.attrs.get("class", "") + " form-control"

        html = render_to_string(
            self.template_name,
            {
                "field": self.field,
                "widget_then_label": isinstance(
                    self.field.field.widget, forms.CheckboxInput
                ),
                "label_tag": self.field.label_tag(
                    label_suffix=self.label_suffix,
                    attrs=(
                        {"class": " ".join(extra_classes + extra_label_classes)}
                    ),
                ),
                "css_classes": self.field.css_classes(
                    extra_classes=extra_classes
                    + [
                        "widget--%s"
                        % (self.field.field.widget.__class__.__name__.lower(),)
                    ]
                ),
            },
        )

        if isinstance(widget, forms.RadioSelect):
            html = html.replace(
                'type="radio"',
                'class="form-check-input" type="radio"',
            )
        elif isinstance(widget, forms.CheckboxSelectMultiple):
            html = html.replace(
                'type="checkbox"',
                'class="form-check-input" type="checkbox"',
            )
        return html
