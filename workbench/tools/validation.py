from django.core.exceptions import ValidationError


def raise_if_errors(errors, exclude=()):
    if errors:
        if set(exclude) & errors.keys():
            raise ValidationError(", ".join(str(e) for e in errors.values()))
        raise ValidationError(errors)
