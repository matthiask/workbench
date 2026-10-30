import datetime as dt

from ninja import Field, Schema
from pydantic import model_validator


class MilestoneIn(Schema):
    id: int | None = Field(
        default=None,
        description="ID of an existing milestone of the project to update,"
        " leave out for new milestones.",
    )
    key: str | None = Field(
        default=None,
        min_length=1,
        description="Identifies a new milestone inside this import. Planned work"
        " references it in its milestone field.",
    )
    title: str = Field(min_length=1, max_length=200)
    date: dt.date
    phase_starts_on: dt.date | None = None
    estimated_total_hours: float = Field(default=0, ge=0)


class PlannedWorkIn(Schema):
    id: int | None = Field(
        default=None,
        description="ID of existing planned work of the project to update,"
        " leave out for new work. Fields left out keep their values.",
    )
    # Required for new work, see below
    title: str | None = Field(default=None, min_length=1, max_length=200)
    user: str | None = Field(
        default=None, description="Short name of the person doing the work."
    )
    service_type: str | None = Field(
        default=None, description="Title of the primary service type."
    )
    offer: str | None = Field(
        default=None, description="Code of the offer this work belongs to."
    )
    milestone: str | int | None = Field(
        default=None,
        description="Key of a milestone in this import or ID of an existing milestone.",
    )
    weeks: list[dt.date] | None = Field(
        default=None,
        min_length=1,
        description="Mondays of the weeks during which the work is done. Weeks"
        " do not have to be consecutive.",
    )
    planned_hours: float | None = Field(
        default=None, ge=0.1, description="Total hours over all weeks."
    )
    is_provisional: bool = Field(
        default=True,
        description="Provisional work hasn't been confirmed with the person"
        " doing the work yet.",
    )
    notes: str = ""

    @model_validator(mode="after")
    def new_work_is_complete(self):
        """Updates only need the changed fields, new work needs everything"""
        if self.id is None and (
            missing := [field for field in REQUIRED if getattr(self, field) is None]
        ):
            raise ValueError(f"New planned work requires {', '.join(missing)}.")
        return self


REQUIRED = ["title", "user", "service_type", "weeks", "planned_hours"]


class PlanningImport(Schema):
    milestones: list[MilestoneIn] = []
    planned_work: list[PlannedWorkIn] = []
    delete_milestones: list[int] = Field(
        default=[], description="IDs of milestones of the project to delete."
    )
    delete_planned_work: list[int] = Field(
        default=[], description="IDs of planned work of the project to delete."
    )


class PlannedWorkPatch(Schema):
    """Changes of single planned work, fields left out keep their values"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    user: str | None = None
    service_type: str | None = None
    offer: str | None = Field(
        default=None, description="Offer code, null removes the offer."
    )
    milestone: int | None = Field(
        default=None, description="Milestone ID, null removes the milestone."
    )
    weeks: list[dt.date] | None = Field(default=None, min_length=1)
    planned_hours: float | None = Field(default=None, ge=0.1)
    is_provisional: bool | None = None
    notes: str | None = None


def planning_import_schema(*, users, service_types, offers):
    """JSON schema of a planning import which only allows the given values"""
    schema = PlanningImport.model_json_schema()
    work = schema["$defs"]["PlannedWorkIn"]
    properties = work["properties"]
    properties["user"]["anyOf"][0]["enum"] = users
    properties["service_type"]["anyOf"][0]["enum"] = service_types
    properties["offer"]["anyOf"][0]["enum"] = offers
    # Tell LLMs which fields new work needs
    work["description"] = "New planned work (without id) requires: " + ", ".join(
        REQUIRED
    )
    return schema
