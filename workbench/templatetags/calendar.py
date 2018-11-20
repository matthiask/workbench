from django import template


register = template.Library()


@register.filter
def calendar(days):
    week = [None] * 7
    key = days[0].day.isocalendar()[:2]
    for day in days:
        if day.day.isocalendar()[:2] != key:
            key = day.day.isocalendar()[:2]
            yield week[:]
            week[:] = [None] * 7
        week[day.day.weekday()] = day
    yield week[:]
