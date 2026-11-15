import hashlib
import secrets

from django.core.exceptions import PermissionDenied
from django.utils.crypto import salted_hmac

from .models import Installation


class TokenConflict(Exception):
    pass


def token_revision(installation):
    return salted_hmac('omda.sync-token-revision', f'{installation.pk}:{installation.sync_token_hash}').hexdigest()


def rotate_sync_token(user, installation, *, revision=None):
    """Apply the existing Django Admin token format and hash-only storage."""
    if not user.is_active or not user.is_staff or not user.is_superuser or not user.has_perm('subscriptions.change_installation'):
        raise PermissionDenied
    if revision is not None and not secrets.compare_digest(revision, token_revision(installation)):
        raise TokenConflict
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    updated = Installation.objects.filter(pk=installation.pk, sync_token_hash=installation.sync_token_hash).update(
        sync_token_hash=digest,
    )
    if not updated:
        raise TokenConflict
    return token
