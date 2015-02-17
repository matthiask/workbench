from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _

import vanilla


class ToolsMixin(object):
    def get_template_names(self):
        """
        Returns a list of template names to use when rendering the response.
        If `.template_name` is not specified, then defaults to the following
        pattern: "{app_label}/{model_name}{template_name_suffix}.html"
        """
        if self.template_name is not None:
            return [self.template_name]

        if self.model is not None and self.template_name_suffix is not None:
            return [
                "%s/%s%s.html" % (
                    self.model._meta.app_label,
                    self.model._meta.object_name.lower(),
                    self.template_name_suffix
                ),
                "tools/object%s.html" % self.template_name_suffix,
            ]

        msg = "'%s' must either define 'template_name' or 'model' and " \
            "'template_name_suffix', or override 'get_template_names()'"
        raise ImproperlyConfigured(msg % self.__class__.__name__)

    @property
    def meta(self):
        return self.model._meta


class ListView(ToolsMixin, vanilla.ListView):
    paginate_by = 10

    def get_queryset(self):
        self.root_queryset = self.model.objects.all()

        q = self.request.GET.get('q')
        return self.root_queryset.search(q) if q else self.root_queryset.all()

    @cached_property
    def root_queryset_count(self):
        return self.root_queryset.count()


class DetailView(ToolsMixin, vanilla.DetailView):
    pass


class CreateView(ToolsMixin, vanilla.CreateView):
    def form_valid(self, form):
        self.object = form.save()
        messages.success(
            self.request,
            _('%(class)s "%(object)s" has been successfully created.') % {
                'class': self.object._meta.verbose_name,
                'object': self.object,
            })
        return HttpResponseRedirect(self.get_success_url())


class UpdateView(ToolsMixin, vanilla.UpdateView):
    def form_valid(self, form):
        self.object = form.save()
        messages.success(
            self.request,
            _('%(class)s "%(object)s" has been successfully updated.') % {
                'class': self.object._meta.verbose_name,
                'object': self.object,
            })
        return HttpResponseRedirect(self.get_success_url())


class DeleteView(ToolsMixin, vanilla.DeleteView):
    def allow_delete(self, silent=False):
        if not silent:
            messages.error(
                self.request,
                _('Deletion of %(class)s "%(object)s" is not allowed.') % {
                    'class': self.object._meta.verbose_name,
                    'object': self.object,
                })

        return False

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.allow_delete(silent=False):
            return HttpResponseRedirect(self.object.get_absolute_url())
        context = self.get_context_data()
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.allow_delete(silent=True):
            return HttpResponseRedirect(self.object.get_absolute_url())
        self.object.delete()
        return self.success()

    def success(self):
        messages.success(
            self.request,
            _('%(class)s "%(object)s" has been successfully deleted.') % {
                'class': self.model._meta.verbose_name,
                'object': self.object,
            })
        return HttpResponseRedirect(self.model().urls.url('list'))
