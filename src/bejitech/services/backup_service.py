"""Encrypted backup and restore with integrity verification.

File format (.bjtbackup):
    MAGIC (11 bytes) | header length (4 bytes, big-endian) | header JSON | nonce (12) | AES-256-GCM ciphertext
The header (KDF parameters, app/schema version) is authenticated as associated data.
The plaintext is a ZIP containing the database snapshot, logos, delivery notes and
manifest.json (SHA-256 of every file + the data encryption key so the backup restores
on another Mac). The key is derived from the backup password with Argon2id.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import sqlite3
import struct
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import select

from bejitech import __version__
from bejitech.core.errors import BackupError, KeyStoreError, ValidationError
from bejitech.core.timeutil import utcnow_iso
from bejitech.db.migrations import LATEST_VERSION, current_version, migrate
from bejitech.db.models import BackupHistory
from bejitech.security import crypto, passwords
from bejitech.services.common import audit

MAGIC = b"BJTBACKUP1\n"
EXTENSION = ".bjtbackup"
MIN_BACKUP_PASSWORD = 8


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BackupService:
    def __init__(self, ctx):
        self.ctx = ctx

    # ---------- create ----------
    def _require_sqlite(self) -> None:
        if getattr(self.ctx.db, "is_postgres", False):
            raise BackupError("Backup files are made by the desktop app. The web version is backed up "
                              "automatically by the hosting service.")

    def _snapshot_db(self) -> bytes:
        tmp = Path(tempfile.mkdtemp()) / "snap.db"
        try:
            src = sqlite3.connect(self.ctx.paths.database)
            dst = sqlite3.connect(tmp)
            with dst:
                src.backup(dst)  # consistent online snapshot
            src.close()
            dst.close()
            return tmp.read_bytes()
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)

    def _payload(self) -> tuple[bytes, int]:
        dek = self.ctx.keystore.load()
        if not dek:
            raise KeyStoreError("Encryption key unavailable; cannot create a restorable backup.")
        files: dict[str, bytes] = {"bejitech.db": self._snapshot_db()}
        for folder in ("logos", "delivery_notes"):
            base = self.ctx.paths.root / folder
            if base.exists():
                for f in sorted(base.rglob("*")):
                    if f.is_file():
                        files[f.relative_to(self.ctx.paths.root).as_posix()] = f.read_bytes()
        conn = sqlite3.connect(self.ctx.paths.database)
        schema = current_version(conn)
        conn.close()
        manifest = {"app_version": __version__, "schema_version": schema, "created_at": utcnow_iso(),
                    "files": {name: _sha(data) for name, data in files.items()},
                    "data_key": base64.b64encode(dek).decode()}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)
            z.writestr("manifest.json", json.dumps(manifest, indent=1))
        return buf.getvalue(), schema

    def create_backup(self, destination_dir: Path, password: str, kind: str = "MANUAL") -> Path:
        self._require_sqlite()
        if len(password) < MIN_BACKUP_PASSWORD:
            raise ValidationError(f"Backup password must be at least {MIN_BACKUP_PASSWORD} characters.")
        destination_dir = Path(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)
        payload, schema = self._payload()
        params = passwords.new_kdf_params()
        header = json.dumps({"kdf": "argon2id", "kdf_params": params, "app_version": __version__,
                             "schema_version": schema, "created_at": utcnow_iso()}).encode()
        key = passwords.derive_key(password, params)
        nonce, ct = crypto.encrypt(key, payload, header)
        stamp = utcnow_iso().replace(":", "").replace("-", "")
        out = destination_dir / f"Bejitech_{kind.lower()}_{stamp}{EXTENSION}"
        blob = MAGIC + struct.pack(">I", len(header)) + header + nonce + ct
        tmp = out.with_suffix(".part")
        tmp.write_bytes(blob)
        os.replace(tmp, out)
        verified = True
        try:
            self.verify_backup(out, password)
        except BackupError:
            verified = False
        with self.ctx.db.session() as s:
            s.add(BackupHistory(kind=kind, file_path=str(out), file_sha256=_sha(blob), size_bytes=len(blob),
                                schema_revision=str(schema), app_version=__version__, verified=int(verified),
                                verified_at=utcnow_iso() if verified else None, created_at=utcnow_iso()))
            audit(s, self.ctx.user_id, "BACKUP_CREATED", "backup", None, file=out.name, verified=verified)
        if not verified:
            raise BackupError(f"Backup written to {out} but verification FAILED. Do not rely on it.")
        return out

    # ---------- read / verify ----------
    @staticmethod
    def _open(path: Path, password: str) -> tuple[dict, zipfile.ZipFile, dict]:
        blob = Path(path).read_bytes()
        if not blob.startswith(MAGIC):
            raise BackupError("This is not a Bejitech backup file.")
        try:
            (hlen,) = struct.unpack(">I", blob[len(MAGIC):len(MAGIC) + 4])
            start = len(MAGIC) + 4
            header_bytes = blob[start:start + hlen]
            header = json.loads(header_bytes)
            nonce = blob[start + hlen:start + hlen + 12]
            ct = blob[start + hlen + 12:]
        except Exception as exc:  # noqa: BLE001
            raise BackupError("The backup file is damaged.") from exc
        key = passwords.derive_key(password, header["kdf_params"])
        try:
            payload = crypto.decrypt(key, nonce, ct, header_bytes)
        except KeyStoreError as exc:
            raise BackupError("Wrong backup password, or the file has been damaged or altered.") from exc
        z = zipfile.ZipFile(io.BytesIO(payload))
        manifest = json.loads(z.read("manifest.json"))
        return header, z, manifest

    def verify_backup(self, path: Path, password: str) -> dict:
        """Decrypt, check every file hash and run SQLite's integrity check. Returns the manifest summary."""
        header, z, manifest = self._open(path, password)
        for name, digest in manifest["files"].items():
            if _sha(z.read(name)) != digest:
                raise BackupError(f"Integrity check failed for {name}.")
        tmpdir = Path(tempfile.mkdtemp())
        try:
            db = tmpdir / "check.db"
            db.write_bytes(z.read("bejitech.db"))
            conn = sqlite3.connect(db)
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("products", "licenses", "customers", "sales")}
            conn.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        if result != "ok":
            raise BackupError(f"Database integrity check failed: {result}")
        return {"created_at": manifest["created_at"], "app_version": manifest["app_version"],
                "schema_version": manifest["schema_version"], "files": len(manifest["files"]), "counts": counts}

    # ---------- restore ----------
    def restore_backup(self, path: Path, password: str) -> Path:
        self._require_sqlite()
        """Replace all data with the backup. A safety backup (same password) is made first.
        The application must be restarted afterwards. Returns the safety backup path."""
        summary = self.verify_backup(path, password)
        if int(summary["schema_version"]) > LATEST_VERSION:
            raise BackupError("This backup was made by a newer version of the app. Please update first.")
        safety = self.create_backup(self.ctx.paths.backups, password, kind="PRE_RESTORE")
        _, z, manifest = self._open(path, password)
        root = self.ctx.paths.root
        self.ctx.db.dispose()
        stage = Path(tempfile.mkdtemp(dir=root))
        try:
            for name in manifest["files"]:
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
            for folder in ("logos", "delivery_notes"):
                if (root / folder).exists():
                    shutil.rmtree(root / folder)
                if (stage / folder).exists():
                    shutil.move(str(stage / folder), str(root / folder))
                else:
                    (root / folder).mkdir()
            for suffix in ("-wal", "-shm"):
                Path(str(self.ctx.paths.database) + suffix).unlink(missing_ok=True)
            os.replace(stage / "bejitech.db", self.ctx.paths.database)
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        self.ctx.keystore.save(base64.b64decode(manifest["data_key"]))
        migrate(self.ctx.paths.database, self.ctx.paths.backups)
        self.ctx.cipher = None
        # audit in the restored database
        from bejitech.db.engine import Database
        self.ctx.db = Database(self.ctx.paths.database)
        with self.ctx.db.session() as s:
            audit(s, None, "RESTORE", "backup", None, file=Path(path).name, safety_backup=safety.name)
        return safety

    def history(self) -> list[dict]:
        with self.ctx.db.session() as s:
            return [{"created_at": b.created_at, "kind": b.kind, "file_path": b.file_path,
                     "size_bytes": b.size_bytes, "verified": bool(b.verified)}
                    for b in s.scalars(select(BackupHistory).order_by(BackupHistory.id.desc()))]
