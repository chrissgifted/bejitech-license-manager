"""Authenticated encryption for licence keys (AES-256-GCM)."""
from __future__ import annotations

import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from bejitech.core.errors import KeyStoreError
from bejitech.security.masking import normalize_key

NONCE_SIZE = 12
KEY_SIZE = 32
_CHECK_PLAINTEXT = b"bejitech-dek-check-v1"


def generate_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def encrypt(key: bytes, plaintext: bytes, aad: bytes | None = None) -> tuple[bytes, bytes]:
    nonce = os.urandom(NONCE_SIZE)
    return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes | None = None) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise KeyStoreError(
            "Data could not be decrypted. The encryption key is wrong or the data was altered."
        ) from exc


def _subkey(dek: bytes, purpose: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=purpose).derive(dek)


class CipherBox:
    """Encrypts licence keys with the data encryption key (DEK)."""

    def __init__(self, dek: bytes):
        if len(dek) != KEY_SIZE:
            raise KeyStoreError("Invalid encryption key length.")
        self._enc_key = _subkey(dek, b"bejitech/license-key-encryption")
        self._mac_key = _subkey(dek, b"bejitech/license-key-fingerprint")

    def encrypt_license_key(self, license_key: str, record_uuid: str) -> tuple[bytes, bytes]:
        nonce, ct = encrypt(self._enc_key, license_key.encode("utf-8"), record_uuid.encode())
        return ct, nonce

    def decrypt_license_key(self, ciphertext: bytes, nonce: bytes, record_uuid: str) -> str:
        return decrypt(self._enc_key, nonce, ciphertext, record_uuid.encode()).decode("utf-8")

    def fingerprint(self, license_key: str) -> str:
        return hmac.new(self._mac_key, normalize_key(license_key).encode(), hashlib.sha256).hexdigest()

    def make_check(self) -> bytes:
        nonce, ct = encrypt(self._enc_key, _CHECK_PLAINTEXT, b"check")
        return nonce + ct

    def verify_check(self, blob: bytes) -> bool:
        try:
            return decrypt(self._enc_key, blob[:NONCE_SIZE], blob[NONCE_SIZE:], b"check") == _CHECK_PLAINTEXT
        except KeyStoreError:
            return False
