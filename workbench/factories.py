import datetime as dt
import types

from django.utils import timezone

import factory
from faker import Factory
from faker.providers import address

from workbench.accounts.models import Team, User
from workbench.awt.models import Absence, Employment, WorkingTimeModel, Year
from workbench.contacts.models import Organization, Person, PostalAddress
from workbench.credit_control.models import CreditEntry, Ledger
from workbench.deals.models import AttributeGroup, ClosingType, Deal, ValueType
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.logbook.models import Break, LoggedCost, LoggedHours
from workbench.offers.models import Offer
from workbench.projects.models import Project, Service
from workbench.reporting.models import CostCenter
from workbench.services.models import ServiceType


faker = Factory.create("de")
faker.add_provider(address)


# AWT #########################################################################
class WorkingTimeModelFactory(factory.DjangoModelFactory):
    name = "Test"

    class Meta:
        model = WorkingTimeModel


class YearFactory(factory.DjangoModelFactory):
    working_time_model = factory.SubFactory(WorkingTimeModelFactory)
    year = factory.LazyAttribute(lambda a: dt.date.today().year)
    january = 30
    february = 30
    march = 30
    april = 30
    may = 30
    june = 30
    july = 30
    august = 30
    september = 30
    october = 30
    november = 30
    december = 30
    working_time_per_day = 8

    class Meta:
        model = Year


# ACCOUNTS ####################################################################
class UserFactory(factory.DjangoModelFactory):
    is_active = True
    _full_name = factory.LazyFunction(faker.name)
    _short_name = factory.Sequence(lambda n: "user%d" % n)
    email = factory.LazyAttribute(lambda obj: "%s@example.com" % obj._short_name)
    language = "en"
    working_time_model = factory.SubFactory(WorkingTimeModelFactory)

    class Meta:
        model = User


class TeamFactory(factory.DjangoModelFactory):
    name = factory.Sequence(lambda n: "Team %d" % n)

    class Meta:
        model = Team


class EmploymentFactory(factory.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    percentage = 100
    vacation_weeks = 5

    class Meta:
        model = Employment


class AbsenceFactory(factory.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    reason = "vacation"
    starts_on = factory.LazyAttribute(lambda a: dt.date.today())
    days = 1

    class Meta:
        model = Absence


# CONTACTS ####################################################################
class PersonFactory(factory.DjangoModelFactory):
    given_name = "Vorname"
    family_name = "Nachname"
    primary_contact = factory.SubFactory(UserFactory)

    class Meta:
        model = Person


class OrganizationFactory(factory.DjangoModelFactory):
    primary_contact = factory.SubFactory(UserFactory)
    name = "The Organization Ltd"

    class Meta:
        model = Organization


class PostalAddressFactory(factory.DjangoModelFactory):
    type = "work"
    person = factory.SubFactory(PersonFactory)
    street = factory.LazyFunction(faker.street_name)
    house_number = factory.LazyFunction(
        lambda: str(faker.random_digit_not_null_or_empty())
    )
    postal_code = factory.LazyFunction(faker.postcode)
    city = factory.LazyFunction(faker.city)

    class Meta:
        model = PostalAddress


# PROJECTS ####################################################################
class ProjectFactory(factory.DjangoModelFactory):
    customer = factory.SubFactory(OrganizationFactory)
    contact = factory.LazyAttribute(
        lambda obj: PersonFactory.create(organization=obj.customer)
    )
    owned_by = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: "Project %d" % n)
    type = Project.ORDER

    class Meta:
        model = Project


class ServiceFactory(factory.DjangoModelFactory):
    project = factory.SubFactory(ProjectFactory)
    title = "Any service"
    service_hours = 0

    class Meta:
        model = Service


# OFFERS ######################################################################
class OfferFactory(factory.DjangoModelFactory):
    project = factory.SubFactory(ProjectFactory)
    owned_by = factory.SubFactory(UserFactory)

    class Meta:
        model = Offer


# INVOICES ####################################################################
class InvoiceFactory(factory.DjangoModelFactory):
    customer = factory.SubFactory(OrganizationFactory)
    contact = factory.LazyAttribute(
        lambda obj: PersonFactory.create(organization=obj.customer)
    )
    owned_by = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: "Invoice %d" % n)
    type = Invoice.FIXED
    invoiced_on = factory.LazyAttribute(lambda a: dt.date.today())

    class Meta:
        model = Invoice


class RecurringInvoiceFactory(factory.DjangoModelFactory):
    customer = factory.SubFactory(OrganizationFactory)
    contact = factory.LazyAttribute(
        lambda obj: PersonFactory.create(organization=obj.customer)
    )
    owned_by = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: "Invoice %d" % n)
    periodicity = "yearly"

    class Meta:
        model = RecurringInvoice


# SERVICES ####################################################################
def service_types():
    service_types = [("consulting", 250), ("production", 180), ("administration", 130)]

    return types.SimpleNamespace(
        **{
            row[0]: ServiceType.objects.create(
                title=row[0], hourly_rate=row[1], position=idx
            )
            for idx, row in enumerate(service_types)
        }
    )


# LOGBOOK #####################################################################
class LoggedHoursFactory(factory.DjangoModelFactory):
    service = factory.SubFactory(ServiceFactory)
    created_by = factory.SubFactory(UserFactory)
    rendered_by = factory.SubFactory(UserFactory)
    rendered_on = factory.LazyAttribute(lambda a: dt.date.today())
    hours = 1

    class Meta:
        model = LoggedHours


class LoggedCostFactory(factory.DjangoModelFactory):
    service = factory.SubFactory(ServiceFactory)
    created_by = factory.SubFactory(UserFactory)
    rendered_by = factory.LazyAttribute(lambda obj: obj.created_by)
    rendered_on = factory.LazyAttribute(lambda a: dt.date.today())
    cost = 10

    class Meta:
        model = LoggedCost


class BreakFactory(factory.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    starts_at = factory.LazyAttribute(
        lambda a: (timezone.now() - dt.timedelta(seconds=3600))
    )
    ends_at = factory.LazyAttribute(lambda a: timezone.now())
    description = "Brk"

    class Meta:
        model = Break


# CREDIT CONTROL ##############################################################
class LedgerFactory(factory.DjangoModelFactory):
    name = "bank account"
    parser = "zkb-csv"

    class Meta:
        model = Ledger


class CreditEntryFactory(factory.DjangoModelFactory):
    ledger = factory.SubFactory(LedgerFactory)
    reference_number = factory.Sequence(lambda n: "payment{}".format(n))
    value_date = factory.LazyAttribute(lambda a: dt.date.today())
    total = 1
    payment_notice = factory.Sequence(lambda n: "Payment {}".format(n))

    class Meta:
        model = CreditEntry


# DEALS #######################################################################
class ValueTypeFactory(factory.DjangoModelFactory):
    title = "Consulting"

    class Meta:
        model = ValueType


class AttributeGroupFactory(factory.DjangoModelFactory):
    class Meta:
        model = AttributeGroup


class ClosingTypeFactory(factory.DjangoModelFactory):
    class Meta:
        model = ClosingType


class DealFactory(factory.DjangoModelFactory):
    customer = factory.SubFactory(OrganizationFactory)
    contact = factory.LazyAttribute(
        lambda obj: PersonFactory.create(organization=obj.customer)
    )
    owned_by = factory.SubFactory(UserFactory)
    title = "Some deal"

    class Meta:
        model = Deal


# REPORTING ###################################################################
class CostCenterFactory(factory.DjangoModelFactory):
    title = "Anything"

    class Meta:
        model = CostCenter
