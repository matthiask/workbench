import datetime as dt

from django.template import Context, Template, TemplateSyntaxError
from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.templatetags.workbench import field_value_pairs, link_or_none


class TemplateTagsTest(TestCase):
    def test_mark_current(self):
        """{% mark_current %}"""
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
        """Invalid mark_current usage (no argument)"""
        with self.assertRaises(TemplateSyntaxError):
            Template("{% load mark_current %}{% mark_current %}")

    def test_bar(self):
        """{% bar %} template tag"""
        t = Template("{% load workbench %}{% bar value one %}")
        self.assertEqual(
            t.render(Context({"value": 10, "one": 100})),
            '<div class="progress progress-line" title="10%">'
            '<div class="progress-bar bg-success" role="progressbar"'
            ' style="width:10%"></div></div>',  # noqa
        )
        self.assertEqual(
            t.render(Context({"value": 80, "one": 100})),
            '<div class="progress progress-line" title="80%"><div class="progress-bar bg-success" role="progressbar" style="width:75%"></div><div class="progress-bar bg-caveat" role="progressbar" style="width:5%"></div></div>',  # noqa
        )
        self.assertEqual(
            t.render(Context({"value": 150, "one": 100})),
            '<div class="progress progress-line" title="150%"><div class="progress-bar bg-success" role="progressbar" style="width:50.0%"></div><div class="progress-bar bg-caveat" role="progressbar" style="width:16.67%"></div><div class="progress-bar bg-danger" role="progressbar" style="width:33.33%"></div></div>',  # noqa
        )

    def test_pie(self):
        """{% pie %} template tag"""
        t = Template("{% load workbench %}{% pie 1 3 %}")
        self.assertEqual(
            t.render(Context()),
            """<svg width="22" height="22" class="pie bad" style="display: inline-block">
  <circle r="10" cx="10" cy="10" class="pie-circle" />
  <path d="M 10 0 A 10 10 0 0 1 18.66025403784439 14.999999999999998 L 10 10 z" class="pie-arc" />
</svg>""",  # noqa
        )

        t = Template("{% load workbench %}{% pie 1 0 %}")
        self.assertEqual(
            t.render(Context()),
            """<svg width="22" height="22" class="pie bad" style="display: inline-block">
  <circle r="10" cx="10" cy="10" class="pie-circle" />
  <path d="M 10 0 A 10 10 0 0 1 10.0 0.0 L 10 10 z" class="pie-arc" />
</svg>""",  # noqa
        )

    def test_link_or_none(self):
        """{% link_or_none %} with special values"""
        self.assertEqual(link_or_none(0), 0)
        self.assertEqual(str(link_or_none(None)), "&ndash;")

    def test_field_value_pairs(self):
        """The |field_value_pairs filter does what it should"""
        deactivate_all()
        absence = factories.AbsenceFactory.create(starts_on=dt.date(2020, 1, 1))
        pairs = dict(field_value_pairs(absence))

        self.assertEqual(pairs["Starts on"], "01.01.2020")
        self.assertEqual(pairs["Ends on"], None)
        self.assertEqual(pairs["Reason"], "vacation")
        self.assertEqual(pairs["Is vacation"], "yes")
