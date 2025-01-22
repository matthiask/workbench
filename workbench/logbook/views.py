from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workbench.projects.forms import ProjectAutocompleteForm
from workbench.templatetags.workbench import h


def create(request, *, viewname):
    if not request.is_ajax():
        return redirect("/")
    form = ProjectAutocompleteForm(
        request.POST if request.method == "POST" else None, logging=True
    )
    params = request.GET.urlencode()
    if form.is_valid():
        if form.cleaned_data["service"]:
            params += "&service={}".format(form.cleaned_data["service"].pk)
        return redirect(
            "{}?{}".format(form.cleaned_data["project"].urls[viewname], params)
        )
    return render(
        request,
        "generic/select_object.html",
        {
            "form": form,
            "title": _("Select project for logging"),
            "links": [
                {
                    "title": h(project),
                    "url": f"{project.urls[viewname]}?{params}",
                    "attrs": "data-ajaxmodal",
                    "shortcut": (idx + 1) % 10 if idx < 10 else None,
                    "is_pinned": getattr(project, "is_pinned", False),
                }
                for idx, project in enumerate(request.user.active_projects)
            ],
        },
    )
