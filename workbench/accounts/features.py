from enum import Enum, auto
from functools import wraps

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _


def feature_required(feature):
    def decorator(view):
        @wraps(view)
        def require_feature(request, *args, **kwargs):
            if request.user.features[feature]:
                return view(request, *args, **kwargs)
            messages.warning(request, _("Feature not available"))
            return HttpResponseRedirect("/")

        return require_feature

    return decorator


class FEATURES(str, Enum):
    AWT_WARNING_INDIVIDUAL = "AWT_WARNING_INDIVIDUAL"
    AWT_WARNING_ALL = "AWT_WARNING_ALL"
    BOOKKEEPING = "BOOKKEEPING"
    BREAKS_NAG = "BREAKS_NAG"
    CAMPAIGNS = "CAMPAIGNS"
    COFFEE = "COFFEE"
    CONTROLLING = "CONTROLLING"
    DEALS = "DEALS"
    EXPENSES = "EXPENSES"
    FOREIGN_CURRENCIES = "FOREIGN_CURRENCIES"
    GLASSFROG = "GLASSFROG"
    LABOR_COSTS = "LABOR_COSTS"
    LATE_LOGGING = "LATE_LOGGING"
    LATE_LOGGING_NAG = "LATE_LOGGING_NAG"
    PLANNING = "PLANNING"
    PRIDE = "PRIDE"
    PROJECTED_INVOICES = "PROJECTED_INVOICES"
    WORKING_TIME_CORRECTION = "WORKING_TIME_CORRECTION"


LABELS = {
    FEATURES.AWT_WARNING_INDIVIDUAL: {
        "label": _("Individual annual working time warning"),
    },
    FEATURES.AWT_WARNING_ALL: {
        "label": _("Annual working time warnings for all"),
    },
    FEATURES.BOOKKEEPING: {
        "label": _("Bookkeeping"),
    },
    FEATURES.BREAKS_NAG: {
        "label": capfirst(_("Breaks nag")),
        "help_text": _("Warn if user is taking an insufficient amount of breaks."),
    },
    FEATURES.CAMPAIGNS: {
        "label": capfirst(_("campaigns")),
        "help_text": _("Campaigns allow grouping projects."),
    },
    FEATURES.COFFEE: {
        "label": _("Coffee break"),
        "help_text": _("Receive regular invites for a coffee break?"),
    },
    FEATURES.CONTROLLING: {
        "label": _("Controlling"),
    },
    FEATURES.DEALS: {
        "label": _("Deals"),
        "help_text": _("Allow managing the acquisition pipeline."),
    },
    FEATURES.EXPENSES: {
        "label": _("Expenses"),
        "help_text": _("Personal expense tracking and reimbursement."),
    },
    FEATURES.FOREIGN_CURRENCIES: {
        "label": _("Foreign currencies for expenses"),
    },
    FEATURES.GLASSFROG: {
        "label": _("GlassFrog integration"),
    },
    FEATURES.LABOR_COSTS: {
        "label": capfirst(_("labor costs")),
    },
    FEATURES.LATE_LOGGING: {
        "label": _("Late logging"),
        "help_text": _("Hours and absences can be added and changed late."),
    },
    FEATURES.LATE_LOGGING_NAG: {
        "label": _("Late logging nag"),
        "help_text": _("Annoy users when they are late with their logging."),
    },
    FEATURES.PLANNING: {
        "label": capfirst(_("planning")),
    },
    FEATURES.PRIDE: {
        "label": capfirst(_("pride")),
    },
    FEATURES.PROJECTED_INVOICES: {
        "label": capfirst(_("projected invoices")),
    },
    FEATURES.WORKING_TIME_CORRECTION: {
        "label": capfirst(_("Working time correction")),
        "help_text": _(
            "This user may add and change absences of type Working time correction."
        ),
    },
}


class F(Enum):
    ALWAYS = auto()
    NEVER = auto()
    USER = auto()


bookkeeping_only = feature_required(FEATURES.BOOKKEEPING)
controlling_only = feature_required(FEATURES.CONTROLLING)
deals_only = feature_required(FEATURES.DEALS)
labor_costs_only = feature_required(FEATURES.LABOR_COSTS)
