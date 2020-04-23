from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _, ngettext

from workbench import generic
from workbench.credit_control.forms import AssignCreditEntriesForm


class AccountStatementUploadView(generic.CreateView):
    def get_context_data(self, **kwargs):
        kwargs.setdefault("title", _("Upload account statement"))
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        entries = form.save()
        messages.success(
            self.request,
            ngettext(
                "Created %s credit entry.", "Created %s credit entries.", len(entries)
            )
            % len(entries),
        )
        return redirect("credit_control_creditentry_list")


class AssignCreditEntriesView(generic.CreateView):
    form_class = AssignCreditEntriesForm

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if not form.entries:
            messages.success(
                request, _("All credit entries have already been assigned.")
            )
            return redirect("credit_control_creditentry_list")
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            _("%(class)s have been updated successfully.")
            % {"class": self.model._meta.verbose_name_plural},
        )
        return redirect(".")

    def get_context_data(self, **kwargs):
        kwargs.setdefault("title", _("Assign credit entries"))
        return super().get_context_data(**kwargs)
