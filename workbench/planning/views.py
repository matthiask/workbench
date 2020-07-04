from workbench import generic
from workbench.accounts.models import Team, User
from workbench.planning import reporting
from workbench.projects.models import Project


class ProjectPlanningView(generic.DetailView):
    model = Project
    template_name = "planning/project_planning.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            planning_data=reporting.project_planning(self.object), **kwargs
        )


class UserPlanningView(generic.DetailView):
    model = User
    template_name = "planning/user_planning.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            planning_data=reporting.user_planning(self.object), **kwargs
        )


class TeamPlanningView(generic.DetailView):
    model = Team
    template_name = "planning/team_planning.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            planning_data=reporting.team_planning(self.object), **kwargs
        )
