from stories.models import Story
from tools.views import DetailView


class StoryMixin(object):
    model = Story


class StoryAjaxDetailView(StoryMixin, DetailView):
    template_name_suffix = '_ajaxdetail'
