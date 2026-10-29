import datetime as dt
import secrets

from django.conf import settings
from ninja import Router
from ninja.security import HttpBearer

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.reporting.cash_data_api import cash_data
from workbench.reporting.key_data_api import key_data_for_month
from workbench.tools.validation import last_month_range


def jsonable(value):
    """Convert report data to JSON: dates as ISO strings, decimals as numbers"""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, dt.date):
        return value.isoformat()
    if value is None or isinstance(value, (str, int)):
        return value
    return float(value)


class ReportingToken(HttpBearer):
    """The reporting APIs authenticate with a static bearer token"""

    def authenticate(self, request, token):
        expected = settings.KEY_DATA_API_TOKEN
        return bool(expected) and secrets.compare_digest(
            token.encode(), expected.encode()
        )


# The static token for integrations, or users with the controlling feature
# like in the web interface
router = Router(
    auth=[ReportingToken(), *user_auth(feature=FEATURES.CONTROLLING)],
    tags=["reporting"],
)


@router.get("/key-data/")
def key_data(request):
    """Key data of the last month"""
    return jsonable(key_data_for_month(last_month_range()[0]))


@router.get("/cash-data/")
def cash_data_api(request, date: dt.date | None = None):
    """Cash data as of the given date, today by default"""
    return jsonable(cash_data(date or dt.date.today()))
