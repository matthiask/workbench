import types

import factory
from faker import Factory

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.invoices.models import Invoice
from workbench.offers.models import Offer, Service
from workbench.projects.models import Project, Task
from workbench.services.models import ServiceType


faker = Factory.create("de")


# ACCOUNTS ####################################################################
class UserFactory(factory.DjangoModelFactory):
    is_active = True
    _full_name = factory.LazyFunction(faker.name)
    _short_name = factory.Sequence(lambda n: "user%d" % n)
    email = factory.LazyAttribute(lambda obj: "%s@example.com" % obj._short_name)

    class Meta:
        model = User


# CONTACTS ####################################################################
class PersonFactory(factory.DjangoModelFactory):
    full_name = "Vorname Nachname"
    primary_contact = factory.SubFactory(UserFactory)

    class Meta:
        model = Person


class OrganizationFactory(factory.DjangoModelFactory):
    primary_contact = factory.SubFactory(UserFactory)

    class Meta:
        model = Organization


# PROJECTS ####################################################################
class ProjectFactory(factory.DjangoModelFactory):
    customer = factory.SubFactory(OrganizationFactory)
    contact = factory.LazyAttribute(
        lambda obj: PersonFactory.create(organization=obj.customer)
    )
    owned_by = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: "Project %d" % n)
    status = Project.WORK_IN_PROGRESS

    class Meta:
        model = Project


class TaskFactory(factory.DjangoModelFactory):
    class Meta:
        model = Task


# OFFERS ######################################################################
class OfferFactory(factory.DjangoModelFactory):
    project = factory.SubFactory(ProjectFactory)
    owned_by = factory.SubFactory(UserFactory)

    class Meta:
        model = Offer


class ServiceFactory(factory.DjangoModelFactory):
    offer = factory.SubFactory(OfferFactory)
    effort_hours = 0

    class Meta:
        model = Service


# INVOICES ####################################################################
class InvoiceFactory(factory.DjangoModelFactory):
    customer = factory.SubFactory(OrganizationFactory)
    owned_by = factory.SubFactory(UserFactory)

    class Meta:
        model = Invoice


# SERVICES ####################################################################
def service_types():
    SERVICE_TYPES = [("consulting", 250), ("production", 180), ("administration", 130)]

    return types.SimpleNamespace(**{
        row[0]: ServiceType.objects.create(
            title=row[0], billing_per_hour=row[1], position=idx
        )
        for idx, row in enumerate(SERVICE_TYPES)
    })
