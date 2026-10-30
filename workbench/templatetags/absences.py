from django import template


register = template.Library()


@register.filter
def absence_reason(absence, user):
    """The reason the user may see, sickness is hidden from others"""
    return absence.reason_for(user)[1]


@register.filter
def absence_description(absence, user):
    return absence.description_for(user)


@register.filter
def absence_title(absence, user):
    return absence.description_for(user) or absence.reason_for(user)[1]
