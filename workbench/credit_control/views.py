from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from workbench import generic
from workbench.credit_control.forms import AssignCreditEntriesForm


class AccountStatementUploadView(generic.CreateView):
    def get_context_data(self, **kwargs):
        kwargs.setdefault("override_title", _("upload account statement"))
        return super().get_context_data(**kwargs)


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

    def post(self, request, *args, **kwargs):
        form = self.get_form(data=request.POST, files=request.FILES)
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            _("%(class)s have been successfully updated.")
            % {"class": self.model._meta.verbose_name_plural},
        )
        return redirect(".")

    def get_context_data(self, **kwargs):
        kwargs.setdefault("override_title", _("assign credit entries"))
        return super().get_context_data(**kwargs)
