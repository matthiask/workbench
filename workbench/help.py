"""The user documentation in docs/ as help pages

English in ``name.md``, German in ``name.de.md``, shown in the user's
language. The Markdown files link each other relatively (``hours.md``),
which works on GitHub; here the links lead to the help pages instead.

The help explains Workbench, not how an installation uses it: its own rules
(naming, rates, who plans whom) belong into its handbook.
"""

import re

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from markdown_it import MarkdownIt


# Page → file in docs/ per language, in the order of the navigation, the
# README is the start page
_NAMES = {
    "": "README",
    "hours": "hours",
    "absences": "absences",
    "offers": "offers",
    "invoices": "invoices",
    "reports": "reports",
    "cli": "cli",
    "shortcuts": "shortcuts",
}
PAGES = {
    "en": {page: f"{name}.md" for page, name in _NAMES.items()},
    "de": {page: f"{name}.de.md" for page, name in _NAMES.items()},
}
# The docs come from the repository, not from users: HTML like <kbd> is fine
_markdown = MarkdownIt("commonmark", {"html": True}).enable("table")
_link = re.compile(r'href="([^":#/]+\.md)(#[^"]*)?"')
_heading = re.compile(r"<h([2-4])>(.*?)</h\1>")


def _anchor(match):
    """IDs for headings like GitHub's, so that links to sections work in
    both places"""
    text = re.sub(r"<[^>]+>|&[a-z]+;", "", match[2]).strip().lower()
    slug = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
    return f'<h{match[1]} id="{slug}">{match[2]}</h{match[1]}>'


def url(page):
    return reverse("help", args=[page]) if page else reverse("help")


def _language():
    return "de" if get_language() == "de" else "en"


def _title(line):
    return re.sub(r"[*_]", "", line.removeprefix("# ")).strip()


def chapters(page, language):
    """All pages in their order for the navigation above each, the current
    one marked"""
    result = []
    for key, file in PAGES[language].items():
        with (settings.BASE_DIR / "docs" / file).open() as f:
            title = _title(f.readline())
        result.append({"url": url(key), "title": title, "current": key == page})
    return result


def render_page(page, language):
    pages = PAGES[language]
    text = (settings.BASE_DIR / "docs" / pages[page]).read_text()
    title = _title(text.split("\n", 1)[0])
    files = {file: key for key, file in pages.items()}

    def link(match):
        if match[1] not in files:
            return match[0]
        return f'href="{url(files[match[1]])}{match[2] or ""}"'

    html = _heading.sub(_anchor, _markdown.render(text))
    html = re.sub(r"^<h1>.*?</h1>\n", "", html, count=1)  # The page's title
    return title, mark_safe(_link.sub(link, html))


def help_page(request, page=""):
    language = _language()
    if page not in PAGES[language]:
        raise Http404
    title, html = render_page(page, language)
    return render(
        request,
        "help.html",
        {"chapters": chapters(page, language), "title": title, "html": html},
    )
