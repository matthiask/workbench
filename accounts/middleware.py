from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import connections
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _


def set_user_name(username):
    connections['default'].cursor().execute(
        'SET SESSION application_name TO %s',
        [username])


def login_required(get_response):
    def middleware(request):
        if request.user.is_authenticated:
            set_user_name(request.user.get_full_name())
            return get_response(request)

        set_user_name('Anonymous')

        if request.path.startswith('/accounts/'):
            return get_response(request)

        messages.info(
            request,
            _('Please authenticate.'))

        response = HttpResponseRedirect(reverse('login'))
        response.set_signed_cookie(
            'next', request.get_full_path(), salt='next')
        return response

    return middleware
