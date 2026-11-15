import re

from django.test import TestCase

from workbench import factories
from workbench.help import PAGES


class HelpTest(TestCase):
    def assertPages(self, language):
        for page in PAGES[language]:
            with self.subTest(language=language, page=page):
                response = self.client.get(f"/help/{page}/" if page else "/help/")
                self.assertEqual(response.status_code, 200)
                # The docs link each other, every link leads to a help page
                self.assertEqual(
                    re.findall(r'href="[^"]*\.md', response.content.decode()), []
                )
                # All chapters above each page, in order, the current one
                # marked
                chapters = re.findall(
                    r'<a href="(/help/[^"]*)"', response.content.decode()
                )
                self.assertEqual(
                    chapters[: len(PAGES[language])],
                    [f"/help/{p}/" if p else "/help/" for p in PAGES[language]],
                )
                self.assertContains(response, 'aria-current="page"', count=1)

    def test_english(self):
        self.client.force_login(factories.UserFactory.create(language="en"))
        response = self.client.get("/help/")
        self.assertContains(response, '<h1 class="mb-0">Help</h1>', html=True)
        self.assertContains(response, 'href="/help/shortcuts/"')
        self.assertPages("en")
        # Our docs, HTML like the keys of the shortcuts works
        self.assertContains(
            self.client.get("/help/shortcuts/"), "<kbd>Ctrl-Shift-P</kbd>"
        )
        self.assertEqual(self.client.get("/help/missing/").status_code, 404)

    def test_german(self):
        self.client.force_login(factories.UserFactory.create(language="de"))
        response = self.client.get("/help/")
        self.assertContains(response, '<h1 class="mb-0">Hilfe</h1>', html=True)
        self.assertContains(response, 'href="/help/shortcuts/"')
        self.assertPages("de")

    def test_shortcuts_redirect(self):
        """The old page of the keyboard shortcuts is a chapter now"""
        self.client.force_login(factories.UserFactory.create())
        self.assertRedirects(
            self.client.get("/shortcuts/"),
            "/help/shortcuts/",
            fetch_redirect_response=False,
        )

    def test_anchors(self):
        """Headings have IDs like on GitHub, links to sections work"""
        self.client.force_login(factories.UserFactory.create(language="de"))
        response = self.client.get("/help/hours/")
        self.assertContains(response, 'href="#die-zeitmarken-seite"')
        self.assertContains(response, '<h2 id="die-zeitmarken-seite">')
        self.assertContains(response, '<h2 id="zeitmarken">')
