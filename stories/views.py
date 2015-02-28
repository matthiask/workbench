from services.forms import RenderedServiceForm
from stories.models import Story
from tools.views import DetailView


class StoryMixin(object):
    model = Story


class StoryDetailView(StoryMixin, DetailView):
    template_name_suffix = '_detail'

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            form=RenderedServiceForm(),
            **kwargs)
