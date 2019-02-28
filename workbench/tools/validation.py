from django.core.exceptions import ValidationError


def raise_if_errors(errors, exclude=()):
    if errors:
        if set(exclude) & errors.keys():
            raise ValidationError(", ".join(errors.values()))
        raise ValidationError(errors)
