from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string


def render_to_pdf(request, template, context=None, *, filename):
    html = render_to_string(template, context, request=request)
    return generate_pdf_response(html, filename=filename)


def generate_pdf_response(html, *, filename):
    from io import BytesIO  # noqa: PLC0415

    import bs4  # noqa: PLC0415
    import weasyprint  # noqa: PLC0415

    soup = bs4.BeautifulSoup(html, "html.parser")

    for img in soup.find_all("img"):
        if (src := img.get("src")) and src.startswith(("/media", "/static")):
            img["src"] = img["src"][1:]

    wp = weasyprint.HTML(string=str(soup), base_url=str(settings.BASE_DIR))
    with BytesIO() as buf:
        wp.write_pdf(buf, presentational_hints=True)
        return HttpResponse(
            buf.getvalue(),
            content_type="aplication/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
