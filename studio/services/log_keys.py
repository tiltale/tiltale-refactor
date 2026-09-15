"""Protecting study logs with the project's key pair (see ETHICS.md).

Settings → Advanced → Protect logs generates a key pair once. The public key is stored with the
project and copied into ``/dist/log-key.pem``; ``log.php`` then encrypts every event it receives.
The private key is handed to the researcher once, as a download, and never stored: only whoever
has that file can read the logs, so a copied or leaked ``dist/logs/`` folder is unreadable.

The scheme, mirrored line for line by ``runtime/log.php``: one fresh AES-256-GCM key per event,
wrapped with RSA-OAEP (SHA-1, OpenSSL's default). One encrypted line looks like
``{"enc": <wrapped key>, "iv": ..., "tag": ..., "data": ...}``, all base64.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENCRYPTED_KEYS: frozenset[str] = frozenset({"enc", "iv", "tag", "data"})
_OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None)


class LockedLog(ValueError):
    """The file is encrypted and the private key has not been provided."""


def generate_key_pair() -> tuple[str, str]:
    """A new RSA-3072 pair as ``(private_pem, public_pem)``."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_pem: bytes = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public_pem: bytes = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem.decode("ascii"), public_pem.decode("ascii")


def fingerprint(public_pem: str) -> str:
    """Short SHA-256 fingerprint of the public key, to recognize a key file: ``a1b2:c3d4:…``."""
    der: bytes = serialization.load_pem_public_key(public_pem.encode("ascii")).public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    digest: str = hashlib.sha256(der).hexdigest()[:32]
    return ":".join(digest[i:i + 4] for i in range(0, len(digest), 4))


def is_encrypted(record: dict[str, Any]) -> bool:
    return ENCRYPTED_KEYS <= set(record)


def encrypt_event(event: dict[str, Any], public_pem: str) -> str:
    """One encrypted log line, exactly as ``log.php`` writes it."""
    key, iv = secrets.token_bytes(32), secrets.token_bytes(12)
    sealed: bytes = AESGCM(key).encrypt(iv, json.dumps(event, ensure_ascii=False).encode("utf-8"), None)
    public = serialization.load_pem_public_key(public_pem.encode("ascii"))
    return json.dumps({
        "enc": base64.b64encode(public.encrypt(key, _OAEP)).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "tag": base64.b64encode(sealed[-16:]).decode("ascii"),
        "data": base64.b64encode(sealed[:-16]).decode("ascii"),
    })


def load_private_key(pem: bytes, public_pem: str) -> RSAPrivateKey:
    """The key from a downloaded key file, checked against the project's public key."""
    try:
        private = serialization.load_pem_private_key(pem, password=None)
    except (ValueError, TypeError):
        raise ValueError("This is not a key file made by TilTale.") from None
    if not isinstance(private, RSAPrivateKey) or fingerprint(_public_pem(private)) != fingerprint(public_pem):
        raise ValueError("This key file belongs to another project.")
    return private


def _public_pem(private: RSAPrivateKey) -> str:
    return private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")


def decrypt_event(record: dict[str, Any], private: RSAPrivateKey) -> dict[str, Any]:
    try:
        key: bytes = private.decrypt(base64.b64decode(record["enc"]), _OAEP)
        plain: bytes = AESGCM(key).decrypt(
            base64.b64decode(record["iv"]), base64.b64decode(record["data"]) + base64.b64decode(record["tag"]), None
        )
        event: Any = json.loads(plain)
    except Exception:  # a wrong key, a damaged line or a line that was tampered with all look the same
        raise ValueError("This line could not be decrypted with the project's key.") from None
    if not isinstance(event, dict):
        raise ValueError("A decrypted line must be a JSON object.")
    return event


# The unlocked key lives only in this process, behind a random token in a browser-session cookie;
# restarting the studio locks Results again. The private key never touches the disk or the database.
_unlocked: dict[str, RSAPrivateKey] = {}


def unlock(private: RSAPrivateKey) -> str:
    token: str = secrets.token_urlsafe(32)
    _unlocked[token] = private
    return token


def unlocked(token: str | None) -> RSAPrivateKey | None:
    return _unlocked.get(token or "")
