from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import connections
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _


class LoginRequiredMiddleware(object):
    def set_user_name(self, username):
        connections['default'].cursor().execute(
            'SET SESSION application_name TO %s',
            [username])

    def process_request(self, request):
        if request.user.is_authenticated():
            self.set_user_name(request.user.get_full_name())
            return

        self.set_user_name('Anonymous')

        if request.path.startswith('/accounts/'):
            return

        messages.info(
            request,
            _('Please authenticate.'))

        response = HttpResponseRedirect(reverse('login'))
        response.set_signed_cookie(
            'next', request.get_full_path(), salt='next')
        return response
