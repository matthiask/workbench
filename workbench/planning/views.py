from workbench import generic
from workbench.accounts.models import User
from workbench.projects.models import Project


class ProjectPlanningView(generic.DetailView):
    model = Project
    template_name = "planning/project_planning.html"


class UserPlanningView(generic.DetailView):
    model = User
    template_name = "planning/user_planning.html"
