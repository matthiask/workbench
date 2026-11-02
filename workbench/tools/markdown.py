from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt


# Raw HTML is escaped, so the output is safe without sanitising. Line breaks
# are kept like in the plain text before, links are detected.
_notes = (
    MarkdownIt("commonmark", {"breaks": True, "html": False, "linkify": True})
    .enable(["linkify", "strikethrough"])
    .disable(["image"])
)


def render_markdown(text):
    """Render Markdown (e.g. of notes) as HTML"""
    return mark_safe(_notes.render(text or ""))
