from django.utils import timezone
from ninja.errors import HttpError
from ninja.security import HttpBearer

from apps.users.models import ApiToken


class TokenAuth(HttpBearer):
    """`Authorization: Bearer em_…`. No session, so no CSRF."""

    def authenticate(self, request, key):
        token = (
            ApiToken.objects.select_related("user")
            .filter(key_hash=ApiToken.hash(key), user__is_active=True)
            .first()
        )
        if token is None:
            # Stop here rather than fall through to session auth, whose
            # CSRF check would answer with a confusing 403.
            raise HttpError(401, "Invalid or revoked token.")
        ApiToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
        # Views use request.user, same as with a session.
        request.user = token.user
        return token.user


token_auth = TokenAuth()
