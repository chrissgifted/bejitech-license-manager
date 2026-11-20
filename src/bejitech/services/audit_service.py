from __future__ import annotations

from sqlalchemy import or_, select

from bejitech.db.models import AuditLog, User
from bejitech.services.common import audit


class AuditService:
    def __init__(self, ctx):
        self.ctx = ctx

    def log(self, action: str, entity_type: str | None = None, entity_uuid: str | None = None, **details):
        with self.ctx.db.session() as s:
            audit(s, self.ctx.user_id, action, entity_type, entity_uuid, **details)

    def recent(self, limit: int = 500, search: str = "") -> list[dict]:
        with self.ctx.db.session() as s:
            q = select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.user_id)
            if search:
                like = f"%{search}%"
                q = q.where(or_(AuditLog.action.ilike(like), AuditLog.entity_type.ilike(like),
                                AuditLog.details.ilike(like)))
            q = q.order_by(AuditLog.id.desc()).limit(limit)
            return [
                {"occurred_at": a.occurred_at, "user": u or "—", "action": a.action,
                 "entity": a.entity_type or "", "details": a.details or ""}
                for a, u in s.execute(q)
            ]
