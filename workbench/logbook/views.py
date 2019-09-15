from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workbench.projects.forms import ProjectAutocompleteForm


def create(request, *, viewname):
    form = ProjectAutocompleteForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        return redirect(form.cleaned_data["project"].urls[viewname])
    return render(
        request,
        "generic/select_object.html",
        {"form": form, "title": _("Select project for logging")},
    )
