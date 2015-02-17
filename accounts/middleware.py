from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _


class LoginRequiredMiddleware(object):
    def process_request(self, request):
        if request.path.startswith('/accounts/'):
            return
        if request.user.is_authenticated():
            return

        messages.info(
            request,
            _('Please authenticate first.'))

        response = HttpResponseRedirect(reverse('login'))
        response.set_signed_cookie('next', request.path, salt='next')
        return response
