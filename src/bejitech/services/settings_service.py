from __future__ import annotations

from bejitech.services.common import all_settings, audit, get_setting, set_setting


class SettingsService:
    def __init__(self, ctx):
        self.ctx = ctx

    def get(self, key: str, default: str = "") -> str:
        with self.ctx.db.session() as s:
            return get_setting(s, key, default)

    def get_int(self, key: str, default: int) -> int:
        try:
            return int(self.get(key, str(default)))
        except ValueError:
            return default

    def all(self) -> dict[str, str]:
        with self.ctx.db.session() as s:
            return all_settings(s)

    def update(self, values: dict[str, str]) -> None:
        with self.ctx.db.session() as s:
            changed = {}
            for key, value in values.items():
                value = "" if value is None else str(value).strip()
                if get_setting(s, key, None) != value:
                    set_setting(s, key, value)
                    changed[key] = value
            if changed:
                audit(s, self.ctx.user_id, "SETTINGS_CHANGED", "settings", None, keys=sorted(changed))

    def seller(self) -> dict[str, str]:
        st = self.all()
        return {
            "name": st.get("seller.name", ""),
            "business_name": st.get("seller.business_name", ""),
            "phone": st.get("seller.phone", ""),
            "email": st.get("seller.email", ""),
            "address": st.get("seller.address", ""),
        }
