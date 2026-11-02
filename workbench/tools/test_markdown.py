from django.test import SimpleTestCase

from workbench.tools.markdown import render_markdown


class MarkdownTest(SimpleTestCase):
    def test_render(self):
        """Notes are rendered as Markdown without allowing HTML"""
        self.assertEqual(render_markdown(""), "")
        self.assertEqual(render_markdown(None), "")
        self.assertEqual(
            render_markdown("**Budget** approved\nby the board"),
            "<p><strong>Budget</strong> approved<br />\nby the board</p>\n",
        )
        self.assertEqual(
            render_markdown("- one\n- two"),
            "<ul>\n<li>one</li>\n<li>two</li>\n</ul>\n",
        )
        self.assertEqual(
            render_markdown("See https://example.com"),
            '<p>See <a href="https://example.com">https://example.com</a></p>\n',
        )
        self.assertEqual(
            render_markdown("<script>alert(1)</script>"),
            "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>\n",
        )
        self.assertEqual(
            render_markdown("[click](javascript:alert(1))"),
            "<p>[click](javascript:alert(1))</p>\n",
        )
        # No images, nothing is loaded from elsewhere
        self.assertEqual(
            render_markdown("![logo](https://example.com/logo.png)"),
            '<p>!<a href="https://example.com/logo.png">logo</a></p>\n',
        )
