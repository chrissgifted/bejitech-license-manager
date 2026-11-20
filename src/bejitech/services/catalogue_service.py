"""Software product catalogue: Publisher → Product line → Version/Edition/Licence type."""
from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from bejitech.core.dto import ProductInput, ProductRow
from bejitech.core.errors import NotFoundError, ValidationError
from bejitech.core.timeutil import utcnow_iso
from bejitech.db.models import Category, LicenseType, Product, ProductLine, Publisher
from bejitech.services.common import audit, clean

MAX_LOGO_BYTES = 5 * 1024 * 1024
LOGO_MAX_SIDE = 600


def _validate_url(url: str | None) -> str | None:
    url = clean(url)
    if url and not (url.lower().startswith("https://") or url.lower().startswith("http://")):
        raise ValidationError("The download URL must start with https:// (or http://).")
    return url


class CatalogueService:
    def __init__(self, ctx):
        self.ctx = ctx

    # ---------- lookups ----------
    def list_publishers(self) -> list[str]:
        with self.ctx.db.session() as s:
            return list(s.scalars(select(Publisher.name).where(Publisher.is_archived == 0).order_by(Publisher.name)))

    def list_categories(self) -> list[str]:
        with self.ctx.db.session() as s:
            return list(s.scalars(select(Category.name).order_by(Category.sort_order, Category.name)))

    def list_product_lines(self, publisher_name: str | None = None) -> list[str]:
        with self.ctx.db.session() as s:
            q = select(ProductLine.name).join(Publisher).where(ProductLine.is_archived == 0)
            if publisher_name:
                q = q.where(func.lower(Publisher.name) == publisher_name.strip().lower())
            return sorted(set(s.scalars(q)))

    def list_license_types(self) -> list[dict]:
        with self.ctx.db.session() as s:
            return [
                {"id": t.id, "code": t.code, "name": t.name, "description": t.description,
                 "allows_multiple_customers": bool(t.allows_multiple_customers),
                 "reassignable": bool(t.reassignable), "default_capacity": t.default_capacity}
                for t in s.scalars(select(LicenseType).order_by(LicenseType.id))
            ]

    def update_license_type(self, type_id: int, allows_multiple_customers: bool, reassignable: bool,
                            default_capacity: int | None = None) -> None:
        with self.ctx.db.session() as s:
            t = s.get(LicenseType, type_id)
            if not t:
                raise NotFoundError("Licence type not found.")
            t.allows_multiple_customers = int(allows_multiple_customers)
            t.reassignable = int(reassignable)
            if default_capacity is not None:
                if default_capacity < 1:
                    raise ValidationError("Default capacity must be at least 1.")
                t.default_capacity = default_capacity
            audit(s, self.ctx.user_id, "UPDATE", "license_type", t.code,
                  allows_multiple_customers=allows_multiple_customers, reassignable=reassignable)

    # ---------- get-or-create helpers ----------
    @staticmethod
    def _publisher(s: Session, name: str) -> Publisher:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Publisher is required.")
        p = s.scalar(select(Publisher).where(func.lower(Publisher.name) == name.lower()))
        if not p:
            now = utcnow_iso()
            p = Publisher(name=name, created_at=now, updated_at=now)
            s.add(p)
            s.flush()
        return p

    @staticmethod
    def _category(s: Session, name: str) -> Category:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Category is required.")
        c = s.scalar(select(Category).where(func.lower(Category.name) == name.lower()))
        if not c:
            c = Category(name=name, sort_order=100)
            s.add(c)
            s.flush()
        return c

    def _line(self, s: Session, publisher: Publisher, category: Category, name: str) -> ProductLine:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Product name (product line) is required.")
        line = s.scalar(select(ProductLine).where(
            ProductLine.publisher_id == publisher.id, func.lower(ProductLine.name) == name.lower()))
        if not line:
            now = utcnow_iso()
            line = ProductLine(publisher_id=publisher.id, category_id=category.id, name=name,
                               created_at=now, updated_at=now)
            s.add(line)
            s.flush()
        elif line.category_id != category.id:
            line.category_id = category.id
        return line

    # ---------- products ----------
    def save_product(self, data: ProductInput) -> int:
        version = (data.version or "").strip()
        edition = (data.edition or "").strip()
        if not version:
            raise ValidationError("Version is required (for example 2024 or 11).")
        if not edition:
            raise ValidationError("Edition is required (for example Professional Plus or Pro).")
        if data.low_stock_threshold < 0:
            raise ValidationError("Low-stock level cannot be negative.")
        if data.purchase_price_minor < 0 or data.selling_price_minor < 0:
            raise ValidationError("Prices cannot be negative.")
        url = _validate_url(data.download_url)
        with self.ctx.db.session() as s:
            if not s.get(LicenseType, data.license_type_id):
                raise ValidationError("Please choose a licence type.")
            pub = self._publisher(s, data.publisher_name)
            cat = self._category(s, data.category_name)
            line = self._line(s, pub, cat, data.product_line_name)
            display = (data.display_name or "").strip() or f"{line.name} {version} {edition}"
            now = utcnow_iso()
            dup = s.scalar(select(Product.id).where(
                Product.product_line_id == line.id, Product.version == version, Product.edition == edition,
                Product.platform == (data.platform or "Windows").strip(),
                Product.license_type_id == data.license_type_id, Product.id != (data.id or 0)))
            if dup:
                raise ValidationError("A product with the same version, edition, platform and licence type already exists.")
            if data.id:
                p = s.get(Product, data.id)
                if not p:
                    raise NotFoundError("Product not found.")
                action = "UPDATE"
            else:
                p = Product(created_at=now)
                action = "CREATE"
            was_verified = bool(p.download_url_verified) and p.download_url == url
            p.product_line_id = line.id
            p.display_name = display
            p.version = version
            p.edition = edition
            p.platform = (data.platform or "Windows").strip()
            p.license_type_id = data.license_type_id
            p.sku_code = clean(data.sku_code)
            p.purchase_price_minor = data.purchase_price_minor
            p.purchase_currency = data.purchase_currency or "TZS"
            p.selling_price_minor = data.selling_price_minor
            p.selling_currency = "TZS"
            p.download_url = url
            p.download_label = clean(data.download_label)
            p.download_url_verified = int(bool(data.download_url_verified and url))
            if p.download_url_verified and not was_verified:
                p.download_url_verified_at = now
            elif not p.download_url_verified:
                p.download_url_verified_at = None
            p.installation_instructions = clean(data.installation_instructions)
            p.activation_instructions = clean(data.activation_instructions)
            p.low_stock_threshold = data.low_stock_threshold
            p.updated_at = now
            if action == "CREATE":
                s.add(p)
            s.flush()
            audit(s, self.ctx.user_id, action, "product", p.uuid, name=display)
            return p.id

    def set_archived(self, product_id: int, archived: bool) -> None:
        with self.ctx.db.session() as s:
            p = s.get(Product, product_id)
            if not p:
                raise NotFoundError("Product not found.")
            p.is_archived = int(archived)
            p.updated_at = utcnow_iso()
            audit(s, self.ctx.user_id, "ARCHIVE" if archived else "UNARCHIVE", "product", p.uuid)

    def set_logo(self, product_id: int, source: Path | str | None) -> str | None:
        """Copy an approved logo (PNG/JPG) into the app data folder. None removes the logo."""
        with self.ctx.db.session() as s:
            p = s.get(Product, product_id)
            if not p:
                raise NotFoundError("Product not found.")
            if source is None:
                p.logo_path = None
                audit(s, self.ctx.user_id, "UPDATE", "product", p.uuid, logo="removed")
                return None
            source = Path(source)
            if not source.exists():
                raise ValidationError("Logo file not found.")
            if source.stat().st_size > MAX_LOGO_BYTES:
                raise ValidationError("Logo file is larger than 5 MB.")
            from PIL import Image, UnidentifiedImageError

            try:
                with Image.open(source) as img:
                    if img.format not in ("PNG", "JPEG"):
                        raise ValidationError("Logos must be PNG or JPG images.")
                    img = img.convert("RGBA")
                    img.thumbnail((LOGO_MAX_SIDE, LOGO_MAX_SIDE))
                    rel = f"logos/{p.uuid}.png"
                    dest = self.ctx.paths.root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    img.save(dest, "PNG")
            except UnidentifiedImageError as exc:
                raise ValidationError("That file is not a readable image.") from exc
            p.logo_path = rel
            p.updated_at = utcnow_iso()
            audit(s, self.ctx.user_id, "UPDATE", "product", p.uuid, logo="updated")
            return rel

    @staticmethod
    def variant_in_session(s: Session, product_id: int, license_type_id: int, user_id: int | None = None) -> Product:
        """Same product (line, version, edition, platform) with another licence type.
        Created automatically, copying prices, links and instructions, if it does not exist yet."""
        base = s.get(Product, product_id)
        if not base:
            raise NotFoundError("Product not found.")
        if base.license_type_id == license_type_id:
            return base
        ltype = s.get(LicenseType, license_type_id)
        if not ltype:
            raise ValidationError("Please choose a licence type.")
        found = s.scalar(select(Product).where(
            Product.product_line_id == base.product_line_id, Product.version == base.version,
            Product.edition == base.edition, Product.platform == base.platform,
            Product.license_type_id == license_type_id))
        if found:
            if found.is_archived:
                found.is_archived = 0
            return found
        now = utcnow_iso()
        clone = Product(
            product_line_id=base.product_line_id, display_name=f"{base.display_name} ({ltype.name})",
            version=base.version, edition=base.edition, platform=base.platform, license_type_id=ltype.id,
            sku_code=None, logo_path=base.logo_path, purchase_price_minor=base.purchase_price_minor,
            purchase_currency=base.purchase_currency, selling_price_minor=base.selling_price_minor,
            selling_currency=base.selling_currency, download_url=base.download_url,
            download_label=base.download_label, download_url_verified=base.download_url_verified,
            download_url_verified_at=base.download_url_verified_at,
            installation_instructions=base.installation_instructions,
            activation_instructions=base.activation_instructions, low_stock_threshold=base.low_stock_threshold,
            created_at=now, updated_at=now)
        s.add(clone)
        s.flush()
        audit(s, user_id, "CREATE", "product", clone.uuid, name=clone.display_name,
              reason="licence type variant")
        return clone

    def variant_for_type(self, product_id: int, license_type_id: int) -> int:
        with self.ctx.db.session() as s:
            return self.variant_in_session(s, product_id, license_type_id, self.ctx.user_id).id

    def logo_file(self, logo_path: str | None) -> Path | None:
        if not logo_path:
            return None
        f = self.ctx.paths.root / logo_path
        return f if f.exists() else None

    def _stock_map(self, s: Session) -> dict[int, tuple[int, int, int]]:
        rows = s.execute(text(
            "SELECT product_id, total_keys, available_activations, allocated_activations FROM v_product_stock"))
        return {r[0]: (r[1], r[2], r[3]) for r in rows}

    @staticmethod
    def _row(p: Product, stock: tuple[int, int, int] | None) -> ProductRow:
        total, avail, alloc = stock or (0, 0, 0)
        return ProductRow(
            id=p.id, uuid=p.uuid, display_name=p.display_name,
            publisher=p.product_line.publisher.name, category=p.product_line.category.name,
            product_line=p.product_line.name, version=p.version, edition=p.edition, platform=p.platform,
            license_type=p.license_type.name, license_type_id=p.license_type_id,
            selling_price_minor=p.selling_price_minor, purchase_price_minor=p.purchase_price_minor,
            purchase_currency=p.purchase_currency, logo_path=p.logo_path, download_url=p.download_url,
            download_label=p.download_label, download_url_verified=bool(p.download_url_verified),
            installation_instructions=p.installation_instructions,
            activation_instructions=p.activation_instructions, low_stock_threshold=p.low_stock_threshold,
            sku_code=p.sku_code, is_archived=bool(p.is_archived), total_keys=total,
            available_activations=avail, allocated_activations=alloc,
        )

    def list_products(self, search: str = "", include_archived: bool = False,
                      publisher: str | None = None, category: str | None = None) -> list[ProductRow]:
        with self.ctx.db.session() as s:
            q = select(Product).join(ProductLine).join(Publisher).join(Category)
            if not include_archived:
                q = q.where(Product.is_archived == 0)
            if publisher:
                q = q.where(Publisher.name == publisher)
            if category:
                q = q.where(Category.name == category)
            if search:
                like = f"%{search.strip()}%"
                q = q.where(Product.display_name.ilike(like) | Publisher.name.ilike(like)
                            | Product.version.ilike(like) | Product.edition.ilike(like)
                            | Category.name.ilike(like) | Product.sku_code.ilike(like))
            q = q.order_by(Publisher.name, ProductLine.name, Product.version.desc(), Product.edition)
            stock = self._stock_map(s)
            return [self._row(p, stock.get(p.id)) for p in s.scalars(q)]

    def get_product(self, product_id: int) -> ProductRow:
        with self.ctx.db.session() as s:
            p = s.get(Product, product_id)
            if not p:
                raise NotFoundError("Product not found.")
            return self._row(p, self._stock_map(s).get(p.id))
