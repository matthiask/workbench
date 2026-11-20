from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workbench import generic
from workbench.logbook.tasks import personnel_administration
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
            "title": _("Select project for logging costs")
            if viewname == "createcost"
            else _("Select project for logging hours"),
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


class LoggedHoursDeleteView(generic.DeleteView):
    template_name = "logbook/loggedhours_confirm_delete.html"

    def get_context_data(self, **kwargs):
        # Deleting someone else's hours is listed in changes_by_others_mails()
        kwargs["reported_to_personnel_administration"] = (
            self.object.rendered_by != self.request.user
            and bool(personnel_administration())
        )
        return super().get_context_data(**kwargs)
