from workbench.projects.models import Project


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


def celebrate(request, logged_hours):
    request.session[SESSION_KEY] = {
        "emoji": project_emoji(logged_hours.service.project),
    }
