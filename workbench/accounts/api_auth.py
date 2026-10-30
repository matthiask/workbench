from django.utils.translation import activate, gettext as _
from ninja.errors import HttpError
from ninja.security import HttpBearer, SessionAuth

from workbench.accounts.features import LABELS
from workbench.accounts.middleware import set_user_name
from workbench.accounts.models import APIToken


def check_feature(user, feature):
    if user and feature and not user.features[feature]:
        raise HttpError(
            403,
            _("You do not have access to the required feature '{feature}'.").format(
                feature=LABELS[feature]["label"]
            ),
        )
    return user


class UserToken(HttpBearer):
    """Personal API tokens, e.g. for the command line interface"""

    def __init__(self, *, feature=None):
        super().__init__()
        self.feature = feature

    def authenticate(self, request, token):
        if token := APIToken.objects.for_secret(token):
            user = token.user
            request.user = user
            request.api_token = token
            # The user middleware only does this for sessions
            activate(user.language)
            set_user_name(user)
            if token.access == APIToken.Access.READ and request.method not in {
                "GET",
                "HEAD",
                "OPTIONS",
            }:
                raise HttpError(
                    403, _("This API token only allows reading, not changes.")
                )
            return check_feature(user, self.feature)
        return None


class UserSession(SessionAuth):
    def __init__(self, *, feature=None):
        super().__init__()
        self.feature = feature

    def authenticate(self, request, key):
        return check_feature(super().authenticate(request, key), self.feature)


def user_auth(*, feature=None):
    """Authenticate users with a token or the session, optionally requiring
    a feature like the web interface's ``feature_required`` decorator

    Tokens come first: The session authentication fails without a CSRF
    token."""
    return [UserToken(feature=feature), UserSession(feature=feature)]
