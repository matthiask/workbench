from datetime import date

from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.core.urlresolvers import reverse, reverse_lazy
from django.utils.translation import ugettext as _

from oauth2client.client import OAuth2WebServerFlow, FlowExchangeError

from accounts.models import User
from tools.views import UpdateView


class UserUpdateView(UpdateView):
    model = User
    fields = ('_full_name', '_short_name', 'email', 'date_of_birth')
    success_url = reverse_lazy('accounts_update')

    def get_object(self):
        return self.request.user


def _oauth2_flow(request):
    flow_kwargs = {
        'client_id': settings.OAUTH2_CLIENT_ID,
        'client_secret': settings.OAUTH2_CLIENT_SECRET,
        'scope': 'email',
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://accounts.google.com/o/oauth2/token',
        'revoke_uri': 'https://accounts.google.com/o/oauth2/revoke',
        'redirect_uri': request.build_absolute_uri(
            reverse('accounts_oauth2_end')),
    }

    return OAuth2WebServerFlow(**flow_kwargs)


def oauth2_start(request):
    flow = _oauth2_flow(request)
    return http.HttpResponseRedirect(flow.step1_get_authorize_url())


def oauth2_end(request):
    flow = _oauth2_flow(request)

    code = request.GET.get('code', None)
    if not code:
        messages.error(
            request,
            _('OAuth2 error: Code missing.'))
        return http.HttpResponseRedirect('/')

    try:
        credentials = flow.step2_exchange(code)
    except FlowExchangeError:
        messages.error(
            request,
            _('OAuth2 error: Credential exchange failed'))
        return http.HttpResponseRedirect('/')

    if credentials.id_token['verified_email']:
        email = credentials.id_token['email']
        new_user = False

        if (not User.objects.filter(email=email).exists()
                and email.endswith('@feinheit.ch')):
            User.objects.create(
                email=email,
                is_active=True,
                is_admin=False,
                date_of_birth=date.today(),
                _short_name='',
                _full_name='',
            )
            messages.success(
                request,
                _('Welcome to FeinTOOL! Please fill in your details.'))
            new_user = True

        user = authenticate(email=email)
        if user and user.is_active:
            login(request, user)

        if new_user:
            return http.HttpResponseRedirect(reverse('accounts_update'))

    return http.HttpResponseRedirect('/')
