from workbench import generic
from workbench.accounts.models import User
from workbench.planning import reporting
from workbench.projects.models import Project


class ProjectPlanningView(generic.DetailView):
    model = Project
    template_name = "planning/project_planning.html"


class UserPlanningView(generic.DetailView):
    model = User
    template_name = "planning/user_planning.html"

    def get_context_data(self, **kwargs):
        pw = reporting.planned_work(users=[self.object])

        return super().get_context_data(planned_work=pw, planning_data=pw, **kwargs)
