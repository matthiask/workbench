from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _

from services.forms import RenderedServiceForm
from services.models import RenderedService
from stories.models import Story
from tools.views import ListView, DetailView, CreateView


class RenderedServiceMixin(object):
    model = RenderedService


class RenderedServiceListView(RenderedServiceMixin, ListView):
    pass


class RenderedServiceDetailView(RenderedServiceMixin, DetailView):
    pass


class RenderedServiceCreateView(RenderedServiceMixin, CreateView):
    form_class = RenderedServiceForm

    def allow_create(self):
        self.story = get_object_or_404(Story, pk=self.kwargs['story'])
        return True

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'rendered_by': self.request.user.pk,
        })
        form_class = self.get_form_class()
        return form_class(data, files, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.created_by = self.request.user
        self.object.story = self.story
        self.object.save()
        messages.success(
            self.request,
            _('%(class)s "%(object)s" has been successfully created.') % {
                'class': self.object._meta.verbose_name,
                'object': self.object,
            })
        return redirect(self.get_success_url())
