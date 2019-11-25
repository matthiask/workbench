from django.core.management import BaseCommand
from django.utils.translation import activate, gettext as _

from workbench.projects.models import Project
from workbench.projects.reporting import project_budget_statistics
from workbench.tools.xlsx import WorkbenchXLSXDocument


class Command(BaseCommand):
    def handle(self, **options):
        stats = sorted(
            project_budget_statistics(
                Project.objects.open().exclude(type=Project.INTERNAL)
            ),
            key=lambda project: project["delta"],
            reverse=True,
        )
        activate("de")

        xlsx = WorkbenchXLSXDocument()
        xlsx.add_sheet("Statistics")
        xlsx.table(
            [
                _("project"),
                _("offered"),
                _("logbook"),
                _("undefined rate"),
                _("third party costs"),
                _("invoiced"),
                _("not archived"),
                _("total hours"),
                _("delta"),
            ],
            [
                (
                    project["project"],
                    project["offered"],
                    project["logbook"],
                    project["effort_hours_with_rate_undefined"],
                    project["third_party_costs"],
                    project["invoiced"],
                    project["not_archived"],
                    project["hours"],
                    project["delta"],
                )
                for project in stats
            ],
        )
        xlsx.workbook.save("project-budget-statistics.xlsx")
