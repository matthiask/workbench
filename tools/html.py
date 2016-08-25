class HtmlInHtml(str):
    pass


def str_html_variant(string, html_callable):
    ret = HtmlInHtml(string)
    ret.__html__ = html_callable
    return ret
