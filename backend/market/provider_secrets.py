"""AEAD secret envelopes; keys live in an owner-mounted private file, never in SQL."""
import base64
import json
import os
import re
import stat
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecretUnavailable(ValueError):
    pass


def keyring():
    path = os.environ.get('METADATA_KEYRING_FILE', '')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
                raise ValueError()
            value = json.loads(stream.read(16385))
        keys = {key: base64.b64decode(secret, validate=True) for key, secret in value['keys'].items()}
        if not 1 <= len(keys) <= 8 or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', k) or len(v) != 32 for k, v in keys.items()):
            raise ValueError()
        if value['active'] not in keys: raise ValueError()
        return value['active'], keys
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise SecretUnavailable('Provider credential storage requires a valid private METADATA_KEYRING_FILE') from None


def encrypt(provider, secret):
    active, keys = keyring()
    nonce = os.urandom(12)
    return active, nonce + AESGCM(keys[active]).encrypt(nonce, secret.encode(), ('metadata:' + provider).encode())


def decrypt(provider, key_id, ciphertext):
    _, keys = keyring()
    try:
        return AESGCM(keys[key_id]).decrypt(ciphertext[:12], ciphertext[12:], ('metadata:' + provider).encode()).decode()
    except Exception:
        raise SecretUnavailable('Provider credential cannot be decrypted with this keyring') from None


def rotate(db):
    from .models import MetadataProvider
    from sqlalchemy import select
    active, _ = keyring()
    count = 0
    for row in db.scalars(select(MetadataProvider).with_for_update()):
        for field, key in [('credential','credential_key_id'), ('pending_credential','pending_key_id')]:
            if getattr(row, field) and getattr(row, key) != active:
                secret = decrypt(row.provider, getattr(row, key), getattr(row, field))
                key_id, encrypted = encrypt(row.provider, secret)
                setattr(row, field, encrypted); setattr(row, key, key_id)
                count += 1
    return count
