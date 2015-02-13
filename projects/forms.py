from django import forms
from django.utils.translation import ugettext

from projects.models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ('customer', 'contact', 'title', 'description')

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
