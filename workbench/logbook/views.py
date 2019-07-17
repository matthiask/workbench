from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workbench.logbook.forms import LoggedHoursPreForm


def createhours(request):
    form = LoggedHoursPreForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        return redirect(form.cleaned_data["project"].urls["createhours"])
    return render(
        request, "modalform.html", {"form": form, "title": _("select a project")}
    )
