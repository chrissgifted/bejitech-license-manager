"""Delivery notes: build the PDF from a sale and keep it linked to the sale."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import select

from bejitech.core.dto import DeliveryNoteRow
from bejitech.core.enums import DeliveryNoteStatus, SaleStatus
from bejitech.core.errors import NotFoundError, ValidationError
from bejitech.core.timeutil import display_date, utcnow_iso
from bejitech.db.models import Customer, DeliveryNote, Sale
from bejitech.pdf.delivery_note import build_delivery_note
from bejitech.services.accounts_service import sale_account_summary
from bejitech.services.common import audit, get_setting
from bejitech.services.sales_service import customer_snapshot, seller_snapshot


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class DeliveryNoteService:
    def __init__(self, ctx):
        self.ctx = ctx

    def _data(self, s, note: DeliveryNote) -> dict:
        cipher = self.ctx.require_cipher()
        sale = note.sale
        items = []
        for it in sale.items:
            p = it.product
            keys = []
            for a in it.allocations:
                lic = a.license
                keys.append((cipher.decrypt_license_key(lic.key_ciphertext, lic.key_nonce, lic.uuid), a.quantity))
            logo = self.ctx.catalogue.logo_file(p.logo_path)
            items.append({
                "product_name": p.display_name, "publisher": p.product_line.publisher.name,
                "edition": p.edition, "version": p.version, "platform": p.platform,
                "license_type": p.license_type.name, "quantity": it.quantity, "keys": keys,
                "download_url": p.download_url,
                "download_label": (p.download_label or "").strip() or f"Download {p.display_name}",
                "installation": p.installation_instructions, "activation": p.activation_instructions,
                "logo": logo,
            })
        return {
            "note_number": note.note_number, "delivery_date": display_date(note.delivery_date),
            "sales_ref": sale.sales_ref, "status": note.status,
            "seller": json.loads(note.seller_snapshot), "customer": json.loads(note.customer_snapshot),
            "items": items, "include_signature": bool(note.include_signature),
            "footer": get_setting(s, "delivery.footer", ""),
            "show_account": get_setting(s, "delivery.show_balance", "1") == "1",
        }

    def _render(self, s, note: DeliveryNote) -> Path:
        rel = f"delivery_notes/{note.delivery_date[:4]}/{note.note_number}.pdf"
        out = self.ctx.paths.root / rel
        build_delivery_note(out, self._data(s, note))
        note.pdf_path = rel
        note.pdf_sha256 = sha256_file(out)
        audit(s, self.ctx.user_id, "DELIVERY_NOTE_GENERATED", "delivery_note", note.uuid,
              number=note.note_number)
        return out

    def generate(self, note_id: int) -> Path:
        with self.ctx.db.session() as s:
            note = s.get(DeliveryNote, note_id)
            if not note:
                raise NotFoundError("Delivery note not found.")
            return self._render(s, note)

    def generate_for_sale(self, sale_id: int) -> Path:
        with self.ctx.db.session() as s:
            note = s.scalar(select(DeliveryNote).where(DeliveryNote.sale_id == sale_id)
                            .order_by(DeliveryNote.revision.desc()).limit(1))
            if not note:
                raise NotFoundError("This sale has no delivery note.")
            return self._render(s, note)

    def pdf_file(self, note_id: int) -> Path:
        """Return the PDF, creating it if it is missing or no longer matches its stored hash."""
        with self.ctx.db.session() as s:
            note = s.get(DeliveryNote, note_id)
            if not note:
                raise NotFoundError("Delivery note not found.")
            if note.pdf_path:
                f = self.ctx.paths.root / note.pdf_path
                if f.exists() and sha256_file(f) == note.pdf_sha256:
                    return f
            return self._render(s, note)

    def new_revision(self, note_id: int) -> int:
        """Re-issue with today's seller and customer details. The old note is marked VOID."""
        with self.ctx.db.session() as s:
            old = s.get(DeliveryNote, note_id)
            if not old:
                raise NotFoundError("Delivery note not found.")
            if old.sale.status == SaleStatus.CANCELLED:
                raise ValidationError("The sale is cancelled; a new delivery note cannot be issued.")
            base = old.note_number.split("-R")[0]
            rev = (s.scalar(select(DeliveryNote.revision).where(DeliveryNote.sale_id == old.sale_id)
                            .order_by(DeliveryNote.revision.desc()).limit(1)) or 1) + 1
            note = DeliveryNote(note_number=f"{base}-R{rev}", sale_id=old.sale_id, revision=rev,
                                delivery_date=old.delivery_date, seller_snapshot=seller_snapshot(s),
                                customer_snapshot=customer_snapshot(old.sale.customer,
                                                                    sale_account_summary(s, old.sale)),
                                include_signature=old.include_signature, status=DeliveryNoteStatus.ISSUED,
                                created_at=utcnow_iso())
            s.add(note)
            old.status = DeliveryNoteStatus.VOID
            old.void_reason = f"Superseded by {note.note_number}"
            s.flush()
            self._render(s, note)
            if old.pdf_path:
                self._render(s, old)  # re-render old one with VOID watermark
            return note.id

    def list_notes(self, search: str = "") -> list[DeliveryNoteRow]:
        with self.ctx.db.session() as s:
            q = select(DeliveryNote, Sale.sales_ref, Customer.full_name, Customer.email) \
                .join(Sale, Sale.id == DeliveryNote.sale_id).join(Customer, Customer.id == Sale.customer_id)
            if search:
                like = f"%{search.strip()}%"
                q = q.where(DeliveryNote.note_number.ilike(like) | Sale.sales_ref.ilike(like)
                            | Customer.full_name.ilike(like))
            q = q.order_by(DeliveryNote.id.desc())
            return [DeliveryNoteRow(n.id, n.note_number, n.sale_id, ref, name, email, n.delivery_date, n.status,
                                    n.pdf_path, n.revision) for n, ref, name, email in s.execute(q)]

    def email_draft(self, note_id: int) -> dict:
        """Prepare an email. mailto: cannot attach files, so the PDF must be attached by hand."""
        note = next((n for n in self.list_notes() if n.id == note_id), None)
        if not note:
            raise NotFoundError("Delivery note not found.")
        seller = self.ctx.settings.seller()
        subject = f"Your software licence - delivery note {note.note_number}"
        body = (f"Dear {note.customer_name},\n\nThank you for your purchase. Please find attached your "
                f"delivery note {note.note_number} with your licence key, download link and installation "
                f"instructions.\n\nKind regards,\n{seller['name']}\n{seller['business_name']}\n"
                f"{seller['phone']}\n{seller['email']}").strip()
        to = note.customer_email or ""
        url = f"mailto:{quote(to)}?subject={quote(subject)}&body={quote(body)}"
        return {"to": to, "subject": subject, "body": body, "url": url}
