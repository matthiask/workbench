"""The Workbench CLI, `wb <noun> <verb>`"""

from wb import (  # noqa: F401 Register the commands
    absences,
    auth,
    contacts,
    deals,
    invoices,
    logbook,
    notes,
    offers,
    planning,
    projects,
    reports,
    services,
    timestamps,
    users,
)
from wb.core import cli


__all__ = ["cli"]
