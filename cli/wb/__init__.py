"""The Workbench CLI, `wb <noun> <verb>`"""

from wb import (  # noqa: F401 Register the commands
    absences,
    auth,
    campaigns,
    contacts,
    deals,
    invoices,
    logbook,
    milestones,
    notes,
    offers,
    planning,
    projects,
    reports,
    search,
    services,
    timestamps,
    users,
)
from wb.core import cli


__all__ = ["cli"]
