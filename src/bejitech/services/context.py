"""AppContext wires the database, key store and services together."""
from __future__ import annotations

from dataclasses import dataclass, field

from bejitech.config.paths import AppPaths
from bejitech.core.errors import KeyStoreError
from bejitech.db.engine import Database
from bejitech.db.migrations import migrate
from bejitech.security.crypto import CipherBox
from bejitech.security.keystore import KeyStore


@dataclass
class AppContext:
    paths: AppPaths
    db: Database
    keystore: KeyStore
    cipher: CipherBox | None = None
    user_id: int | None = None
    _services: dict = field(default_factory=dict)

    @classmethod
    def open(cls, paths: AppPaths, keystore: KeyStore) -> "AppContext":
        paths.ensure()
        migrate(paths.database_target, paths.backups)
        return cls(paths=paths, db=Database(paths.database_target), keystore=keystore)

    def require_cipher(self) -> CipherBox:
        if self.cipher is None:
            raise KeyStoreError("Licence keys are locked. Please sign in again.")
        return self.cipher

    def _get(self, name, factory):
        if name not in self._services:
            self._services[name] = factory(self)
        return self._services[name]

    @property
    def settings(self):
        from bejitech.services.settings_service import SettingsService
        return self._get("settings", SettingsService)

    @property
    def catalogue(self):
        from bejitech.services.catalogue_service import CatalogueService
        return self._get("catalogue", CatalogueService)

    @property
    def inventory(self):
        from bejitech.services.inventory_service import InventoryService
        return self._get("inventory", InventoryService)

    @property
    def allocation(self):
        from bejitech.services.allocation_service import AllocationService
        return self._get("allocation", AllocationService)

    @property
    def customers(self):
        from bejitech.services.customer_service import CustomerService
        return self._get("customers", CustomerService)

    @property
    def sales(self):
        from bejitech.services.sales_service import SalesService
        return self._get("sales", SalesService)

    @property
    def delivery_notes(self):
        from bejitech.services.delivery_note_service import DeliveryNoteService
        return self._get("delivery_notes", DeliveryNoteService)

    @property
    def accounts(self):
        from bejitech.services.accounts_service import AccountsService
        return self._get("accounts", AccountsService)

    @property
    def reports(self):
        from bejitech.services.reporting_service import ReportingService
        return self._get("reports", ReportingService)

    @property
    def auth(self):
        from bejitech.services.auth_service import AuthService
        return self._get("auth", AuthService)

    @property
    def audit(self):
        from bejitech.services.audit_service import AuditService
        return self._get("audit", AuditService)

    @property
    def backup(self):
        from bejitech.services.backup_service import BackupService
        return self._get("backup", BackupService)
