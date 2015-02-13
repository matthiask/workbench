from django.core.urlresolvers import reverse_lazy

from accounts.models import User
from tools.views import UpdateView


class UserUpdateView(UpdateView):
    model = User
    fields = ('_full_name', '_short_name', 'email', 'date_of_birth')
    success_url = reverse_lazy('accounts_update')

    def get_object(self):
        return self.request.user
