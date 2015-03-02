from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

from stories.forms import RenderedServiceForm
from stories.models import Story, RenderedService
from tools.views import ListView, DetailView, CreateView, DeleteView


class StoryMixin(object):
    allow_delete_if_only = {Story}
    model = Story


class StoryDetailView(StoryMixin, DetailView):
    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'rendered_by': self.request.user.pk,
        })
        return RenderedServiceForm(data, files, **kwargs)

    def get_context_data(self, **kwargs):
        if 'form' not in kwargs:
            kwargs['form'] = self.get_form()

        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.allow_create():  # TODO RenderedService, not Story
            return redirect('../')

        form = self.get_form(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.created_by = request.user
            service.story = self.object
            service.save()

            form = self.get_form()

        return self.render_to_response(self.get_context_data(form=form))


class StoryDeleteView(StoryMixin, DeleteView):
    pass


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

        return HttpResponse('Thanks', status=201)  # Created
