import json

from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import classonlymethod
from django.utils.functional import cached_property
from django.utils.text import capfirst
from django.utils.translation import gettext as _, gettext_lazy

import vanilla

from workbench.services.models import ServiceType


class ToolsMixin(object):
    title = None

    @classonlymethod
    def as_view(cls, **initkwargs):
        assert cls.model or initkwargs.get("model"), "model is required for view"
        return super().as_view(**initkwargs)

    @cached_property
    def default_service_types(self):
        return ServiceType.objects.all()

    @cached_property
    def default_service_types_json(self):
        return json.dumps(
            {
                str(type.id): {
                    "effort_type": type.title,
                    "effort_rate": int(type.hourly_rate),
                }
                for type in self.default_service_types
            }
        )

    def get_template_names(self):
        """
        Returns a list of template names to use when rendering the response.
        If `.template_name` is not specified, then defaults to the following
        pattern: "{app_label}/{model_name}{template_name_suffix}.html"
        """
        if self.template_name is not None:
            return [self.template_name]
        return [
            "%s/%s%s.html"
            % (
                self.model._meta.app_label,
                self.model._meta.object_name.lower(),
                self.template_name_suffix,
            ),
            "generic/object%s.html" % self.template_name_suffix,
        ]

    @property
    def meta(self):
        return self.model._meta

    def get_form(self, data=None, files=None, **kwargs):
        kwargs["request"] = self.request
        cls = self.get_form_class()
        return cls(data=data, files=files, **kwargs)

    def get_context_data(self, **kwargs):
        if self.title:
            kwargs.setdefault(
                "title",
                capfirst(
                    self.title
                    % {
                        "object": self.model._meta.verbose_name,
                        "instance": getattr(self, "object", None),
                    }
                ),
            )
        return super().get_context_data(**kwargs)


class ListView(ToolsMixin, vanilla.ListView):
    paginate_by = 100
    search_form_class = None
    show_create_button = True

    @classonlymethod
    def as_view(cls, **initkwargs):
        assert cls.search_form_class or initkwargs.get(
            "search_form_class"
        ), "search_form_class is required for list view"
        return super().as_view(**initkwargs)

    def get(self, request, *args, **kwargs):
        self.search_form = self.search_form_class(request.GET, request=request)
        if not self.search_form.is_valid():
            messages.warning(request, _("Search form was invalid."))
            return HttpResponseRedirect("?error=1")

        if (
            set(request.GET)
            - set(self.search_form.fields)
            # Also see workbench.js
            - {"disposition", "error", "export", "page"}
        ):
            messages.warning(request, _("Invalid parameters to form."))
            return HttpResponseRedirect("?error=1")

        if hasattr(self.search_form, "response"):
            response = self.search_form.response(request, self.get_queryset())
            if response:
                return response
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.search_form.filter(super().get_queryset())


class DetailView(ToolsMixin, vanilla.DetailView):
    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        url = self.model.get_redirect_url(self.object, request)
        if url:
            return redirect(url)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return self.render_to_response(context)


class CreateView(ToolsMixin, vanilla.CreateView):
    title = gettext_lazy("Create %(object)s")

    def dispatch(self, request, *args, **kwargs):
        if not self.model.allow_create(request):
            return (
                render(request, "modal.html") if request.is_ajax() else redirect("../")
            )
        url = self.model.get_redirect_url(None, request)
        if url:
            return redirect(url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        messages.success(
            self.request,
            capfirst(
                _("%(class)s '%(object)s' has been created successfully.")
                % {"class": self.object._meta.verbose_name, "object": self.object}
            ),
        )

        if self.request.is_ajax():
            return HttpResponse("Thanks", status=201)  # Created
        return redirect(self.get_success_url())


class CreateAndUpdateView(CreateView):
    def get_success_url(self):
        return self.object.urls["update"]


class CreateRelatedView(CreateView):
    related_model = None

    def get_form(self, *args, **kwargs):
        instance = get_object_or_404(self.related_model, pk=self.kwargs.pop("pk"))
        attribute = self.related_model.__name__.lower()
        setattr(self, attribute, instance)
        kwargs[attribute] = instance
        return super().get_form(*args, **kwargs)


class UpdateView(ToolsMixin, vanilla.UpdateView):
    title = gettext_lazy("Update %(object)s")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.allow_update(self.object, request):
            return (
                render(request, "modal.html")
                if request.is_ajax()
                else redirect(self.object)
            )
        url = self.model.get_redirect_url(self.object, request)
        if url:
            return redirect(url)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = self.get_form(instance=self.object)
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form = self.get_form(
            data=request.POST, files=request.FILES, instance=self.object
        )
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        self.object = form.save()
        messages.success(
            self.request,
            capfirst(
                _("%(class)s '%(object)s' has been updated successfully.")
                % {"class": self.object._meta.verbose_name, "object": self.object}
            ),
        )
        if self.request.is_ajax():
            return HttpResponse("Thanks", status=202)  # Accepted
        return redirect(self.get_success_url())


class DeleteView(ToolsMixin, vanilla.DeleteView):
    delete_form_class = None
    title = gettext_lazy("Delete %(object)s")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        allow_delete = self.object.allow_delete(self.object, request)
        if allow_delete is True:
            pass  # Fine!
        elif allow_delete is False:
            return (
                render(request, "modal.html")
                if request.is_ajax()
                else redirect(self.object)
            )
        else:
            assert (
                self.delete_form_class
            ), "delete_form_class must be set if allow_delete returns None"

        url = self.model.get_redirect_url(self.object, request)
        if url:
            return redirect(url)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        if self.delete_form_class:
            form = self.delete_form_class(
                request.POST, instance=self.object, request=request
            )
            if form.is_valid():
                form.delete()
            else:
                context = self.get_context_data()
                context["form"] = form
                return self.render_to_response(context)
        else:
            self.object.delete()

        messages.success(
            self.request,
            capfirst(
                _("%(class)s '%(object)s' has been deleted successfully.")
                % {"class": self.model._meta.verbose_name, "object": self.object},
            ),
        )
        if request.is_ajax():
            return HttpResponse("Thanks", status=204)  # No content
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        if self.delete_form_class and self.request.method == "GET":
            kwargs["form"] = self.delete_form_class(
                instance=self.object, request=self.request
            )
        return super().get_context_data(**kwargs)

    def get_success_url(self):
        return self.model.urls["list"]


class AutocompleteView(ToolsMixin, vanilla.ListView):
    filter = None
    label_from_instance = str

    def get(self, request, *args, **kwargs):
        q = request.GET.get("q")
        queryset = self.get_queryset().search(q)
        queryset = (
            self.filter(queryset=queryset, request=request) if self.filter else queryset
        )
        return JsonResponse(
            {
                "results": [
                    {"label": self.label_from_instance(instance), "value": instance.pk}
                    for instance in queryset[:50]
                ]
                if q
                else []
            }
        )
