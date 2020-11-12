import time
from functools import wraps
from urllib.parse import urlencode

from django import forms
from django.forms.utils import flatatt
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext, gettext_lazy as _

from workbench.accounts.models import User


class Textarea(forms.Textarea):
    def __init__(self, attrs=None):
        default_attrs = {"cols": 40, "rows": 5}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


_AUTOCOMPLETE_TEMPLATE = """
<div class="input-group">
  <input type="text" class="form-control" id="%(id)s_pretty"
    value="%(pretty)s" placeholder="%(placeholder)s"
    autocomplete="off"
    data-autocomplete-url="%(url)s" data-autocomplete-id="%(id)s">
  <div class="input-group-append">
    <button type="button" class="btn btn-primary" %(btn_attrs)s
      data-clear="#%(id)s,#%(id)s_pretty">&times;</button>
  </div>
</div>
%(field)s
"""  # noqa


class Autocomplete(forms.TextInput):
    def __init__(self, model, attrs=None, *, params=None):
        super().__init__(attrs)
        self.model = model
        self.params = ("?" + urlencode(params)) if params else ""

    def render(self, name, value, attrs=None, choices=(), renderer=None):
        if value is None:
            value = ""
        final_attrs = self.build_attrs(attrs, {"type": "hidden", "name": name})
        if value != "":
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs["value"] = force_str(self.format_value(value))

        pretty = ""
        try:
            if value:
                pretty = str(self.model.objects.get(pk=value))
        except (self.model.DoesNotExist, TypeError, ValueError):
            pass

        if final_attrs.get("disabled"):
            return super().render(name, pretty or value, attrs, renderer=renderer)

        opts = self.model._meta
        return mark_safe(
            _AUTOCOMPLETE_TEMPLATE
            % {
                "id": final_attrs["id"],
                "url": reverse("%s_%s_autocomplete" % (opts.app_label, opts.model_name))
                + self.params,
                "field": format_html("<input{} />", flatatt(final_attrs)),
                "pretty": escape(pretty),
                "placeholder": capfirst(opts.verbose_name),
                "btn_attrs": "" if value else "disabled",
            }
        )


class WarningsForm:
    """
    Form class mixin which allows implementing validation warnings
    In contrast to Django's ``ValidationError``, these warnings may
    be ignored by checking a checkbox.
    The warnings support consists of the following methods and properties:
    * ``WarningsForm.add_warning(<warning>)``: Adds a new warning message
    * ``WarningsForm.warnings``: A list of warnings or an empty list if there
      are none.
    * ``WarningsForm.is_valid()``: Overridden ``Form.is_valid()``
      implementation which returns ``False`` for otherwise valid forms with
      warnings, if those warnings have not been explicitly ignored (by checking
      a checkbox or by passing ``ignore_warnings=True`` to ``is_valid()``.
    * An additional form field named ``ignore_warnings`` is available - this
      field should only be displayed if ``WarningsForm.warnings`` is non-emtpy.
    """

    def __init__(self, *args, **kwargs):
        super(WarningsForm, self).__init__(*args, **kwargs)

        self.warnings = {}

    def add_warning(self, warning, *, code):
        """
        Adds a new warning, should be called while cleaning the data
        """
        self.warnings[code] = warning

    def is_valid(self, ignore_warnings=False):
        """
        ``is_valid()`` override which returns ``False`` for forms with warnings
        if these warnings haven't been explicitly ignored
        """
        if not super(WarningsForm, self).is_valid():
            return False

        if self.warnings and not self.should_ignore_warnings():
            return False

        return True

    def should_ignore_warnings(self):
        ignore = set(self.data.get(self.ignore_warnings_id, "").split())
        current = set(self.warnings)
        # print("IGNORE", ignore, "CURRENT", current)
        return current <= ignore

    @property
    def ignore_warnings_value(self):
        return " ".join(sorted(self.warnings))

    ignore_warnings_id = "__ig_{}".format(int(time.time() / 10800))


class DateInput(forms.TextInput):
    input_type = "date"


class Form(WarningsForm, forms.Form):
    required_css_class = "required"
    error_css_class = "is-invalid"

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    def apply_simple(self, queryset, *fields):
        data = self.cleaned_data
        for field, value in ((field, data.get(field)) for field in fields):
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset

    def apply_renamed(self, queryset, param, field):
        value = self.cleaned_data.get(param)
        if value:
            return queryset.filter(**{field: value})
        return queryset

    def apply_owned_by(self, queryset, *, attribute="owned_by"):
        value = self.cleaned_data.get(attribute)
        if value == 0:
            return queryset.filter(**{"{}__is_active".format(attribute): False})
        elif value:
            user = self.request.user if value == -1 else value
            return queryset.filter(**{attribute: user})
        return queryset


class ModelForm(WarningsForm, forms.ModelForm):
    user_fields = ()
    default_to_current_user = ()
    required_css_class = "required"
    error_css_class = "is-invalid"

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")

        if self.default_to_current_user:
            instance = kwargs.get("instance")
            if not instance or not instance.pk:
                initial = kwargs.setdefault("initial", {})
                for field in self.default_to_current_user:
                    initial.setdefault(field, self.request.user.pk)

        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if isinstance(field, forms.DateField):
                field.widget = DateInput()

            elif name in self.user_fields:
                field.choices = User.objects.active_choices(
                    include=self.instance
                    and getattr(self.instance, "%s_id" % name, None)
                )

        self.customer_and_contact = all(
            f in self.fields for f in ("customer", "contact")
        )
        if self.customer_and_contact:
            self.fields["customer"].required = False
            self.fields["customer"].help_text = self.fields["customer"].help_text or _(
                "Is automatically filled using the organization's contact."
            )

    def clean(self):
        data = super().clean()

        if self.customer_and_contact:
            if data.get("contact") and not data.get("customer"):
                data["customer"] = data["contact"].organization

            if data.get("customer") and data.get("contact"):
                if data.get("customer") != data.get("contact").organization:
                    raise forms.ValidationError(
                        {
                            "contact": gettext(
                                "The contact %(person)s does not belong to"
                                " %(organization)s."
                            )
                            % {
                                "person": data.get("contact"),
                                "organization": data.get("customer"),
                            }
                        }
                    )

            if not data.get("customer") and "customer" in self.fields:
                raise forms.ValidationError(
                    {"customer": self.fields["customer"].error_messages["required"]},
                    code="required",
                )

            if not data.get("contact"):
                self.add_warning(_("No contact selected."), code="no-contact")

        return data


def add_prefix(prefix):
    def decorator(cls):
        @wraps(cls)
        def fn(*args, **kwargs):
            kwargs.setdefault("prefix", prefix)
            return cls(*args, **kwargs)

        return fn

    return decorator


def querystring(params=None, **kwargs):
    params = params.items() if params else ()
    query = urlencode(
        sorted(
            (key, value)
            for key, value in dict(params, **kwargs).items()
            if key not in {"error"} and value
        )
    )
    return "?%s" % query
