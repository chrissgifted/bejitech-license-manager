"""Argon2id password hashing and key derivation."""
from __future__ import annotations

import base64
import json
import os

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type, hash_secret_raw

# ~0.3–0.6 s on Apple Silicon. Stored inside each hash, so they can be raised later.
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

KDF_DEFAULTS = {"time_cost": 3, "memory_cost": 65536, "parallelism": 4}

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_kdf_params(**overrides) -> dict:
    params = dict(KDF_DEFAULTS)
    params.update(overrides)
    params["salt"] = base64.b64encode(os.urandom(16)).decode()
    return params


def derive_key(secret: str, params: dict) -> bytes:
    """Derive a 256-bit key from a passphrase with Argon2id."""
    return hash_secret_raw(
        secret=secret.encode("utf-8"),
        salt=base64.b64decode(params["salt"]),
        time_cost=int(params["time_cost"]),
        memory_cost=int(params["memory_cost"]),
        parallelism=int(params["parallelism"]),
        hash_len=32,
        type=Type.ID,
    )


def dumps_params(params: dict) -> str:
    return json.dumps(params, sort_keys=True)


def use_fast_parameters_for_tests() -> None:
    """Cheaper Argon2 settings so the test-suite runs quickly. Never called by the app."""
    global _hasher
    _hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)
    KDF_DEFAULTS.update(time_cost=1, memory_cost=8192, parallelism=1)
