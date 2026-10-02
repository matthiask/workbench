import datetime as dt

from django.utils.translation import gettext as _

from workbench.projects.models import Project
from workbench.tools.formats import Z1
from workbench.tools.validation import monday


SESSION_KEY = "logbook_celebration"

PROJECT_TYPE_EMOJIS = {
    Project.ORDER: "✅",
    Project.MAINTENANCE: "🔧",
}

# Keyed by name because internal types are database rows. Unknown or
# renamed internal types get the fallback emoji.
INTERNAL_TYPE_EMOJIS = {
    "Übrige Interna": "🧩",
    "Outreach": "📣",
    "Persönliche Entwicklung": "🌱",
    "Kultur- und Wissens-Leadership": "💡",
    "Controlling": "📊",
    "Ausbildner:innen": "🎓",
}

FALLBACK_EMOJI = "✨"


def project_emoji(project):
    if project.type == Project.INTERNAL:
        return INTERNAL_TYPE_EMOJIS.get(
            project.internal_type.name if project.internal_type else None,
            FALLBACK_EMOJI,
        )
    return PROJECT_TYPE_EMOJIS.get(project.type, FALLBACK_EMOJI)


def _crossed(before, after, threshold):
    return threshold is not None and before < threshold <= after


def _percentage(value, target):
    return round(100 * min(1, float(value / target)), 1) if target else None


def celebrate(request, logged_hours, *, hours_before):
    """Remember a celebration for the next page view

    ``hours_before`` is ``User.hours`` before saving ``logged_hours``.
    Milestones are only celebrated the moment they are crossed.
    """
    today_target = hours_before["today_target"]
    week_target = hours_before["week_target"]
    today = hours_before["today"] + (
        logged_hours.hours if logged_hours.rendered_on == dt.date.today() else Z1
    )
    week = hours_before["week"] + (
        logged_hours.hours if logged_hours.rendered_on >= monday() else Z1
    )

    message = None
    confetti = False
    if _crossed(hours_before["week"], week, week_target):
        message, confetti = _("Week complete 🏁"), True
    elif _crossed(hours_before["today"], today, today_target):
        message, confetti = _("Day complete 🎉"), True
    elif today_target and _crossed(hours_before["today"], today, today_target / 2):
        message = _("Halfway there 💪")

    request.session[SESSION_KEY] = {
        "emoji": project_emoji(logged_hours.service.project),
        "message": message,
        "confetti": confetti,
        "rings_from": {
            name: percentage
            for name, percentage in [
                ("today", _percentage(hours_before["today"], today_target)),
                ("week", _percentage(hours_before["week"], week_target)),
            ]
            if percentage is not None
        },
    }
