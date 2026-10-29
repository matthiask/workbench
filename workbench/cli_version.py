import tomllib

from django.conf import settings
from django.http import JsonResponse
from django.utils.translation import gettext as _


# Bump this when the API changes in ways older CLIs cannot handle
MINIMUM = (0, 2, 0)
# The version in the repository, users of older versions are told to upgrade
LATEST = tomllib.loads((settings.BASE_DIR / "cli" / "pyproject.toml").read_text())[
    "project"
]["version"]


def _parse(version):
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return ()


def cli_version_middleware(get_response):
    """Reject CLIs which are too old, tell outdated ones about the latest
    version"""

    def middleware(request):
        if not (version := request.headers.get("X-Workbench-CLI")):
            return get_response(request)
        if _parse(version) < MINIMUM:
            return JsonResponse(
                {
                    "detail": _(
                        "Your wb is too old for this Workbench, please upgrade"
                        " it: uv tool upgrade workbench-cli"
                    )
                },
                status=426,
            )
        response = get_response(request)
        response["X-Workbench-CLI-Latest"] = LATEST
        return response

    return middleware
