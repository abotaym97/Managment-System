import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def storage_configured():
    folder = getattr(settings, 'OMDA_SIGNING_KEY_DIR', '')
    return bool(folder and getattr(settings, 'OMDA_SIGNING_STORAGE_PASSWORD', '') and Path(folder).is_dir())


def stored_path(installation=None):
    if not storage_configured():
        return None
    name = str(installation.identifier) if installation else 'default'
    return Path(settings.OMDA_SIGNING_KEY_DIR) / (name + '.pem')


def load_key(pem, password):
    if not password:
        raise ValueError('Signing password required')
    key = serialization.load_pem_private_key(pem, password)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError('Ed25519 key required')
    return key


def legacy_configured():
    return bool(os.getenv('OMDA_ISSUER_PRIVATE_KEY') or os.getenv('OMDA_ISSUER_KEY_PASSWORD'))


def get_signing_key(installation=None):
    if (settings.OMDA_SIGNING_KEY_DIR or settings.OMDA_SIGNING_STORAGE_PASSWORD) and not storage_configured():
        raise OSError('Signing storage is unavailable')
    for scope in (installation, None) if installation else (None,):
        path = stored_path(scope)
        if path:
            try:
                pem = path.read_bytes()
            except FileNotFoundError:
                continue
            return load_key(pem, settings.OMDA_SIGNING_STORAGE_PASSWORD.encode())
    if legacy_configured():
        pem = os.environ['OMDA_ISSUER_PRIVATE_KEY'].replace(chr(92) + 'n', chr(10)).encode()
        return load_key(pem, os.environ['OMDA_ISSUER_KEY_PASSWORD'].encode())
    return None


def save_signing_key(key, installation=None):
    path = stored_path(installation)
    if path is None:
        raise ImproperlyConfigured('Signing storage is unavailable')
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(settings.OMDA_SIGNING_STORAGE_PASSWORD.encode()),
    )
    # Publish a complete file atomically without replacing a key another request saved.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
        try:
            tmp.write(pem)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.link(temp_path, path)
        finally:
            tmp.close()
            temp_path.unlink(missing_ok=True)
