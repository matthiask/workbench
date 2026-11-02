from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_POST

from workbench.notes.forms import NoteForm


@require_POST
def add_note(request):
    form = NoteForm(request.POST, request=request)
    url = request.POST.get("next") or "/"
    if form.is_valid():
        note = form.save()
        # Scroll to the new note
        url = f"{url.split('#')[0]}#note-{note.pk}"
    else:
        for msg in form.non_field_errors():
            messages.error(request, msg)
    return HttpResponseRedirect(url)
