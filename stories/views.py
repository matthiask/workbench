from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from stories.forms import RenderedServiceForm, MergeStoryForm
from stories.models import Story, RenderedService
from tools.views import DetailView, UpdateView


class StoryDetailView(DetailView):
    model = Story
    form_class = RenderedServiceForm

    def get_form(self, data=None, files=None):
        return RenderedServiceForm(
            data, files, story=self.object, request=self.request)

    def get_context_data(self, **kwargs):
        if 'form' not in kwargs:
            kwargs['form'] = self.get_form()

        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not RenderedService.allow_create(request):
            return redirect('../')

        form = self.get_form(request.POST, request.FILES)
        if form.is_valid():
            service = form.save()
            form = self.get_form()

            messages.success(
                self.request,
                _("%(class)s '%(object)s' has been successfully created.") % {
                    'class': service._meta.verbose_name,
                    'object': service,
                })

            return redirect(self.object)

        return self.render_to_response(self.get_context_data(form=form))


class StoryMergeView(UpdateView):
    model = Story
    form_class = MergeStoryForm
    template_name = 'tools/object_form.html'

    def get_context_data(self, **kwargs):
        kwargs['title'] = self.object
        return super().get_context_data(**kwargs)
