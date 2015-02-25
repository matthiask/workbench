from django import forms
from django.utils.translation import ugettext, ugettext_lazy as _

from contacts.models import Organization, Person
from projects.models import Project
from tools.forms import ModelForm, Picker


class ProjectSearchForm(forms.Form):
    s = forms.ChoiceField(
        choices=(('', _('All states')),) + Project.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )


class ProjectForm(ModelForm):
    user_fields = ('owned_by',)

    class Meta:
        model = Project
        fields = ('customer', 'contact', 'title', 'description', 'owned_by')
        widgets = {
            'customer': Picker(
                model=Organization,
            ),
            'contact': Picker(
                model=Person,
            ),
        }

    def clean(self):
        data = super().clean()
        if data.get('customer') and data.get('contact'):
            if data.get('customer') != data.get('contact').organization:
                raise forms.ValidationError({
                    'contact': ugettext(
                        'The contact %(person)s does not belong to'
                        '  %(organization)s.'
                    ) % {
                        'person': data.get('contact'),
                        'organization': data.get('customer'),
                    },
                })
        return data
