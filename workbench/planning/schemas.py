import datetime as dt

from ninja import Field, Schema


class MilestoneIn(Schema):
    key: str = Field(
        min_length=1,
        description="Identifies the milestone inside this import. Planned work"
        " references it in its milestone field.",
    )
    title: str = Field(min_length=1, max_length=200)
    date: dt.date
    phase_starts_on: dt.date | None = None
    estimated_total_hours: float = Field(default=0, ge=0)


class PlannedWorkIn(Schema):
    title: str = Field(min_length=1, max_length=200)
    user: str = Field(description="Email address of the person doing the work.")
    service_type: str = Field(description="Title of the primary service type.")
    offer: str | None = Field(
        default=None, description="Code of the offer this work belongs to."
    )
    milestone: str | int | None = Field(
        default=None,
        description="Key of a milestone in this import or ID of an existing milestone.",
    )
    weeks: list[dt.date] = Field(
        min_length=1,
        description="Mondays of the weeks during which the work is done. Weeks"
        " do not have to be consecutive.",
    )
    planned_hours: float = Field(ge=0.1, description="Total hours over all weeks.")
    is_provisional: bool = Field(
        default=True,
        description="Provisional work hasn't been confirmed with the person"
        " doing the work yet.",
    )
    notes: str = ""


class PlanningImport(Schema):
    milestones: list[MilestoneIn] = []
    planned_work: list[PlannedWorkIn] = []


def planning_import_schema(*, users, service_types, offers):
    """JSON schema of a planning import which only allows the given values"""
    schema = PlanningImport.model_json_schema()
    properties = schema["$defs"]["PlannedWorkIn"]["properties"]
    properties["user"]["enum"] = users
    properties["service_type"]["enum"] = service_types
    properties["offer"]["anyOf"][0]["enum"] = offers
    return schema
