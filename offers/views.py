from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _

from offers.forms import ServiceForm
from offers.models import Offer, Service
from tools.pdf import pdf_response
from tools.views import DetailView, CreateView, UpdateView, DeleteView


class OfferPDFView(DetailView):
    model = Offer

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        pdf, response = pdf_response(self.object.code, as_attachment=False)

        pdf.init_offer()
        pdf.process_offer(self.object)
        pdf.generate()

        return response


class CreateServiceView(CreateView):
    model = Service

    def get(self, request, *args, **kwargs):
        if not self.model.allow_create(request):
            return redirect('../')

        self.offer = get_object_or_404(Offer, pk=self.kwargs['pk'])
        if self.offer.status > Offer.IN_PREPARATION:
            messages.error(request, _(
                'Cannot modify an offer which is not in preparation anymore.'
            ))
            return redirect('../')

        form = self.get_form()
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_form(self, data=None, files=None, **kwargs):
        if not hasattr(self, 'offer'):
            self.offer = get_object_or_404(Offer, pk=self.kwargs['pk'])
        return ServiceForm(
            data,
            files,
            offer=self.offer,
            request=self.request,
            **kwargs)

    def get_success_url(self):
        return self.object.urls.url('update')


class UpdateServiceView(UpdateView):
    model = Service
    form_class = ServiceForm

    def get_success_url(self):
        return self.object.offer.get_absolute_url()


class DeleteServiceView(DeleteView):
    model = Service

    def get_success_url(self):
        return self.object.offer.get_absolute_url()


class MoveServiceView(DetailView):
    model = Service

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.model.allow_update(self.object, request):
            return redirect(self.object.offer)
        if self.object.offer.status > Offer.IN_PREPARATION:
            messages.error(request, _(
                'Cannot modify an offer which is not in preparation anymore.'
            ))
            return redirect(self.object.offer)

        pks = list(
            self.object.offer.services.values_list('id', flat=True))
        index = pks.index(self.object.pk)
        if 'up' in request.GET and index > 0:
            pks[index], pks[index - 1] = pks[index - 1], pks[index]
        elif 'down' in request.GET and index < len(pks) - 1:
            pks[index], pks[index + 1] = pks[index + 1], pks[index]

        for index, pk in enumerate(pks):
            Service.objects.filter(pk=pk).update(position=(index + 1) * 10)

        return redirect(self.object.offer)
