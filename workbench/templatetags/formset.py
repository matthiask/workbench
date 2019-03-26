from django import template


register = template.Library()


@register.tag
def formset(parser, token):
    """
    Implements formsets where subforms can be added using the
    ``towel_add_subform`` javascript method::

        {% formset formset "activities" %}
            ... form code
        {% endformset %}
    """

    tokens = token.split_contents()
    nodelist = parser.parse(("endformset",))
    parser.delete_first_token()

    return DynamicFormsetNode(tokens[1], tokens[2], nodelist)


class DynamicFormsetNode(template.Node):
    def __init__(self, formset, slug, nodelist):
        self.formset = template.Variable(formset)
        self.slug = template.Variable(slug)
        self.nodelist = nodelist

    def render(self, context):
        formset = self.formset.resolve(context)
        slug = self.slug.resolve(context)

        result = [str(formset.management_form)]

        with context.push(form_id="%s-empty" % slug, form=formset.empty_form):
            result.append('<script type="text/template" id="%s-empty">' % slug)
            result.append(self.nodelist.render(context))
            result.append("</script>")

        for idx, form in enumerate(formset.forms):
            with context.push(form_id="%s-%s" % (slug, idx), form=form):
                result.append(self.nodelist.render(context))

        return "".join(result)
