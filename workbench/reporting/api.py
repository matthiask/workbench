import datetime as dt
import secrets

from django.conf import settings


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


def has_valid_token(request):
    """The reporting APIs authenticate with a static bearer token"""
    token = settings.KEY_DATA_API_TOKEN
    return bool(token) and secrets.compare_digest(
        request.headers.get("Authorization", ""), f"Bearer {token}"
    )
