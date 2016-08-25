from accounts.models import User
from tools.forms import ModelForm


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ('_full_name', '_short_name', 'email')
