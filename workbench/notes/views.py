from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workbench.notes.forms import NoteForm


def add_note(request):
    if request.method == "POST":
        form = NoteForm(request.POST, request=request)
        if form.is_valid():
            # Scroll to the new note
            url = form.save().get_absolute_url()
            if request.is_ajax():
                return JsonResponse({"redirect": url}, status=299)
            return redirect(url)
    else:
        form = NoteForm(
            request=request,
            initial={
                "content_type": request.GET.get("content_type"),
                "object_id": request.GET.get("object_id"),
            },
        )
    return render(
        request, "notes/note_form.html", {"form": form, "title": _("Add note")}
    )
