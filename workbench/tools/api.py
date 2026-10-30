from django.core.exceptions import ValidationError
from ninja.errors import ValidationError as NinjaValidationError


def full_clean(instance, loc, errors, *, exclude=()):
    """Validate the model instance, add errors located at ``loc`` to
    ``errors``"""
    try:
        instance.full_clean(exclude=exclude)
    except ValidationError as exc:
        errors.extend(
            {"loc": [*loc, field], "msg": message}
            for field, messages in exc.message_dict.items()
            for message in messages
        )


def raise_form_errors(form, *, fields=None):
    """Raise the errors of the invalid form; warnings of the web interface
    are errors too

    ``fields`` maps form fields to their location in the request body."""
    fields = fields or {}
    raise NinjaValidationError(
        [
            {
                "loc": ["body", "data"]
                + ([] if field == "__all__" else fields.get(field, [field])),
                "msg": message,
            }
            for field, messages in form.errors.items()
            for message in messages
        ]
        + [
            {"loc": ["body", "data"], "msg": str(warning)}
            for warning in form.warnings.values()
        ]
    )
