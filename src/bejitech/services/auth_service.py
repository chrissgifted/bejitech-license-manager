"""Administrator authentication and unlocking of the licence-key encryption key."""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from bejitech.core.errors import AuthError, KeyStoreError, ValidationError
from bejitech.core.timeutil import utcnow_iso
from bejitech.db.models import KeyEscrow, User
from bejitech.security import crypto, passwords, totp
from bejitech.security.crypto import CipherBox
from bejitech.services.common import audit, get_setting, set_setting

MAX_FREE_ATTEMPTS = 5
REAUTH_SECONDS = 5 * 60


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check_password_strength(password: str) -> None:
    if len(password) < passwords.MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {passwords.MIN_PASSWORD_LENGTH} characters.")


class AuthService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.last_auth_at = 0.0
        self.username: str | None = None
        self.display_name: str | None = None

    def has_users(self) -> bool:
        with self.ctx.db.session() as s:
            return (s.scalar(select(func.count(User.id))) or 0) > 0

    # ---------- first run ----------
    def create_admin(self, display_name: str, username: str, password: str, recovery_passphrase: str) -> None:
        if self.has_users():
            raise AuthError("An administrator already exists.")
        if not display_name.strip() or not username.strip():
            raise ValidationError("Name and username are required.")
        _check_password_strength(password)
        if len(recovery_passphrase) < 12:
            raise ValidationError("The recovery passphrase must be at least 12 characters.")
        if recovery_passphrase == password:
            raise ValidationError("The recovery passphrase must be different from the password.")
        dek = self.ctx.keystore.load()
        cipher = CipherBox(dek) if dek else None
        if cipher is None or not self._dek_matches(cipher):
            dek = crypto.generate_key()
            cipher = CipherBox(dek)
        now = utcnow_iso()
        with self.ctx.db.session() as s:
            user = User(username=username.strip().lower(), display_name=display_name.strip(),
                        password_hash=passwords.hash_password(password), created_at=now, updated_at=now)
            s.add(user)
            self._write_escrow(s, dek, recovery_passphrase)
            set_setting(s, "security.dek_check", base64.b64encode(cipher.make_check()).decode())
            s.flush()
            audit(s, user.id, "ADMIN_CREATED", "user", user.uuid)
        self.ctx.keystore.save(dek)
        self._signed_in(user.id, user.username, user.display_name, cipher)

    @staticmethod
    def _write_escrow(s, dek: bytes, passphrase: str) -> None:
        params = passwords.new_kdf_params()
        kek = passwords.derive_key(passphrase, params)
        nonce, wrapped = crypto.encrypt(kek, dek, b"recovery")
        row = s.scalar(select(KeyEscrow).where(KeyEscrow.purpose == "RECOVERY"))
        if row is None:
            row = KeyEscrow(purpose="RECOVERY", created_at=utcnow_iso())
            s.add(row)
        row.kdf_params = passwords.dumps_params(params)
        row.wrapped_key = wrapped
        row.nonce = nonce
        row.created_at = utcnow_iso()

    def _dek_matches(self, cipher: CipherBox) -> bool:
        with self.ctx.db.session() as s:
            check = get_setting(s, "security.dek_check", "")
        if not check:
            return True  # nothing encrypted yet
        return cipher.verify_check(base64.b64decode(check))

    def _signed_in(self, user_id, username, display_name, cipher):
        self.ctx.user_id = user_id
        self.ctx.cipher = cipher
        self.username, self.display_name = username, display_name
        self.last_auth_at = time.monotonic()

    # ---------- login ----------
    def login(self, username: str, password: str) -> None:
        """Verify credentials. Raises AuthError. On success the key store is unlocked
        (or KeyStoreError is raised if the key must be recovered with the passphrase)."""
        uid, uname, dname = self.verify_credentials(username, password)
        self.ctx.user_id = uid
        self.username, self.display_name = uname, dname
        self.last_auth_at = time.monotonic()
        self.unlock_keys()

    def verify_credentials(self, username: str, password: str) -> tuple[int, str, str]:
        """Check username and password; returns (user id, username, display name).

        Failed attempts are counted in the database, so the lockout also holds across
        restarts and across the web server's requests."""
        failed = False
        locked_for = 0
        now = datetime.now(timezone.utc)
        with self.ctx.db.session() as s:
            user = s.scalar(select(User).where(User.username == username.strip().lower(), User.is_active == 1))
            if user and user.locked_until:
                until = datetime.fromisoformat(user.locked_until.replace("Z", "+00:00"))
                locked_for = int((until - now).total_seconds())
            if locked_for > 0:
                pass  # refuse without checking the password, so guessing gains nothing
            elif not user or not passwords.verify_password(user.password_hash, password):
                if user:
                    user.failed_logins += 1
                    if user.failed_logins >= MAX_FREE_ATTEMPTS:
                        wait = min(300, 5 * 2 ** (user.failed_logins - MAX_FREE_ATTEMPTS))
                        user.locked_until = _iso(now + timedelta(seconds=wait))
                audit(s, user.id if user else None, "LOGIN_FAILED", "user", None, username=username)
                failed = True  # commit the counter, then raise outside the transaction
            else:
                user.failed_logins = 0
                user.locked_until = None
                user.last_login_at = utcnow_iso()
                if passwords.needs_rehash(user.password_hash):
                    user.password_hash = passwords.hash_password(password)
                audit(s, user.id, "LOGIN", "user", user.uuid)
                uid, uname, dname = user.id, user.username, user.display_name
        if locked_for > 0:
            raise AuthError(f"Too many failed attempts. Please wait {locked_for + 1} seconds.")
        if failed:
            raise AuthError("Incorrect username or password.")
        return uid, uname, dname

    def cipher_from_keystore(self) -> CipherBox:
        """The licence-key cipher from the key store, checked against this database."""
        dek = self.ctx.keystore.load()
        if not dek:
            raise KeyStoreError("The encryption key for licence keys is not available.")
        cipher = CipherBox(dek)
        if not self._dek_matches(cipher):
            raise KeyStoreError("The encryption key does not match this database.")
        return cipher

    # ---------- two-step login (authenticator app) ----------
    @staticmethod
    def new_totp_secret() -> str:
        return totp.new_secret()

    def totp_provisioning_uri(self, secret: str, username: str) -> str:
        return totp.provisioning_uri(secret, username)

    def totp_enabled(self, user_id: int) -> bool:
        with self.ctx.db.session() as s:
            user = s.get(User, user_id)
            return bool(user and user.totp_secret)

    def enable_totp(self, user_id: int, secret: str, code: str) -> None:
        """Turn on two-step login once the user proves their app shows the right code."""
        cipher = self.ctx.require_cipher()
        step = totp.verify(secret, code)
        if step is None:
            raise AuthError("That code is not correct. Check the time on your phone and try again.")
        with self.ctx.db.session() as s:
            user = s.get(User, user_id)
            ct, nonce = cipher.encrypt_license_key(secret, f"totp:{user.uuid}")
            user.totp_secret, user.totp_nonce, user.totp_last_step = ct, nonce, step
            user.updated_at = utcnow_iso()
            audit(s, user.id, "TWO_STEP_ENABLED", "user", user.uuid)

    def verify_totp(self, user_id: int, code: str) -> None:
        """Check a 6-digit code. Each code works once; wrong codes count as failed logins."""
        cipher = self.ctx.require_cipher()
        now = datetime.now(timezone.utc)
        error = None
        with self.ctx.db.session() as s:
            user = s.get(User, user_id)
            if not user or not user.totp_secret:
                raise AuthError("Two-step login is not set up for this account.")
            if user.locked_until and user.locked_until > _iso(now):
                raise AuthError("Too many failed attempts. Please wait and sign in again.")
            secret = cipher.decrypt_license_key(user.totp_secret, user.totp_nonce, f"totp:{user.uuid}")
            step = totp.verify(secret, code)
            if step is None or step <= user.totp_last_step:
                user.failed_logins += 1
                if user.failed_logins >= MAX_FREE_ATTEMPTS:
                    wait = min(300, 5 * 2 ** (user.failed_logins - MAX_FREE_ATTEMPTS))
                    user.locked_until = _iso(now + timedelta(seconds=wait))
                audit(s, user.id, "TWO_STEP_FAILED", "user", user.uuid)
                error = "That code is not correct, or it was already used. Wait for a new code."
            else:
                user.totp_last_step = step
                user.failed_logins = 0
                audit(s, user.id, "TWO_STEP_OK", "user", user.uuid)
        if error:
            raise AuthError(error)

    def check_password(self, user_id: int, password: str) -> None:
        """Re-check the password (before revealing a key). Raises AuthError."""
        with self.ctx.db.session() as s:
            user = s.get(User, user_id)
            ok = bool(user) and passwords.verify_password(user.password_hash, password)
            if not ok:
                audit(s, user_id, "REAUTH_FAILED", "user", None)
        if not ok:
            raise AuthError("Incorrect password.")

    def unlock_keys(self) -> None:
        dek = self.ctx.keystore.load()
        if not dek:
            raise KeyStoreError("The encryption key was not found in the Keychain. "
                                "Enter your recovery passphrase to restore it.")
        cipher = CipherBox(dek)
        if not self._dek_matches(cipher):
            raise KeyStoreError("The encryption key in the Keychain does not match this database. "
                                "Enter your recovery passphrase to restore it.")
        self.ctx.cipher = cipher

    def recover_with_passphrase(self, passphrase: str) -> None:
        with self.ctx.db.session() as s:
            row = s.scalar(select(KeyEscrow).where(KeyEscrow.purpose == "RECOVERY"))
            if not row:
                raise KeyStoreError("No recovery data found.")
            kek = passwords.derive_key(passphrase, json.loads(row.kdf_params))
            try:
                dek = crypto.decrypt(kek, row.nonce, row.wrapped_key, b"recovery")
            except KeyStoreError:
                dek = None
            audit(s, self.ctx.user_id, "KEY_RECOVERED" if dek else "RECOVERY_FAILED", "user", None)
        if dek is None:
            raise AuthError("That recovery passphrase is not correct.")
        cipher = CipherBox(dek)
        if not self._dek_matches(cipher):
            raise KeyStoreError("Recovered key does not match this database.")
        self.ctx.keystore.save(dek)
        self.ctx.cipher = cipher

    def lock(self) -> None:
        self.ctx.cipher = None
        self.last_auth_at = 0.0

    def is_unlocked(self) -> bool:
        return self.ctx.cipher is not None and self.ctx.user_id is not None

    def needs_reauth(self) -> bool:
        return time.monotonic() - self.last_auth_at > REAUTH_SECONDS

    def reauthenticate(self, password: str) -> None:
        with self.ctx.db.session() as s:
            user = s.get(User, self.ctx.user_id)
            ok = bool(user) and passwords.verify_password(user.password_hash, password)
            if not ok:
                audit(s, self.ctx.user_id, "REAUTH_FAILED", "user", None)
        if not ok:
            raise AuthError("Incorrect password.")
        self.last_auth_at = time.monotonic()

    # ---------- changes ----------
    def change_password(self, current: str, new: str) -> None:
        _check_password_strength(new)
        with self.ctx.db.session() as s:
            user = s.get(User, self.ctx.user_id)
            if not user or not passwords.verify_password(user.password_hash, current):
                raise AuthError("Current password is incorrect.")
            user.password_hash = passwords.hash_password(new)
            user.updated_at = utcnow_iso()
            audit(s, user.id, "PASSWORD_CHANGED", "user", user.uuid)

    def change_recovery_passphrase(self, current_password: str, new_passphrase: str) -> None:
        if len(new_passphrase) < 12:
            raise ValidationError("The recovery passphrase must be at least 12 characters.")
        dek = self.ctx.keystore.load()
        if not dek:
            raise KeyStoreError("Encryption key unavailable.")
        with self.ctx.db.session() as s:
            user = s.get(User, self.ctx.user_id)
            if not user or not passwords.verify_password(user.password_hash, current_password):
                raise AuthError("Password is incorrect.")
            self._write_escrow(s, dek, new_passphrase)
            audit(s, user.id, "RECOVERY_PASSPHRASE_CHANGED", "user", user.uuid)
