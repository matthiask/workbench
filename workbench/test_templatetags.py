from django.template import Context, Template, TemplateSyntaxError
from django.test import TestCase


class TemplateTagsTest(TestCase):
    def test_mark_current(self):
        t = Template(
            """
            {% load mark_current %}
            {% mark_current path %}
            <a href="/a/">a</a>
            <a href="/b/">b</a>
            <a class="c" href="/c/">c</a>
            <a class="d" href="/d/">d</a>
            <ul>
            <li><a href="/e/">e</a></li>
            <li class="f"><a href="/f/">f</a></li>
            <li class="g"><a class="g" href="/g/">g</a></li>
            </ul>
            {% endmark_current %}
            """
        )

        for path, exists, notexists in [
            (
                "/a/bla/",
                '<a class="active" href="/a/">a</a>',
                '<a class="active" href="/b/">',
            ),
            (
                "/c/bla/",
                '<a class="c active" href="/c/">c</a>',
                '<a class="d active" href="/d/">',
            ),
            ("/e/bla/", '<li class="active"><a class="active" href="/e/">', ""),
            # Small inconsistency: there is a class so only classes are changed,
            # but the anchor has no class and so gets no .active class either.
            ("/f/bla/", '<li class="f active"><a href="/f/">', ""),
            ("/g/bla/", '<li class="g active"><a class="g active" href="/g/">', ""),
        ]:
            with self.subTest(path=path, exists=exists, notexists=notexists):
                html = t.render(Context({"path": path}))
                self.assertIn(exists, html)
                if notexists:
                    self.assertNotIn(notexists, html)

    def test_invalid(self):
        with self.assertRaises(TemplateSyntaxError):
            Template("{% load mark_current %}{% mark_current %}")
