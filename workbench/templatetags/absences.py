from django import template


register = template.Library()


@register.filter
def absence_description(absence, user):
    """The description of sickness is only shown to some, see
    ``Absence.details_visible_to``"""
    return absence.description_for(user)


@register.filter
def absence_title(absence, user):
    return absence.description_for(user) or absence.get_reason_display()
