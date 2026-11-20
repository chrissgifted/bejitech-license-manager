"""Dashboard figures and reports. All money in TZS."""
from __future__ import annotations

from sqlalchemy import func, select, text

from bejitech.core.dto import Report
from bejitech.core.enums import AllocationStatus, SaleStatus
from bejitech.core.money import format_money
from bejitech.core.timeutil import display_date
from bejitech.db.models import Customer, License, LicenseAllocation, Product, Sale, SaleItem


def _period(date_from, date_to) -> str:
    if date_from or date_to:
        return f"{display_date(date_from) if date_from else 'Start'} – {display_date(date_to) if date_to else 'Today'}"
    return "All time"


class ReportingService:
    def __init__(self, ctx):
        self.ctx = ctx

    def _sale_filter(self, q, date_from, date_to):
        if date_from:
            q = q.where(Sale.sale_date >= date_from)
        if date_to:
            q = q.where(Sale.sale_date <= date_to)
        return q

    def dashboard(self, date_from: str | None = None, date_to: str | None = None) -> dict:
        with self.ctx.db.session() as s:
            stock = s.execute(text(
                "SELECT COALESCE(SUM(total_keys),0), COALESCE(SUM(available_activations),0), "
                "COALESCE(SUM(allocated_activations),0), COALESCE(SUM(fully_allocated_keys),0) "
                "FROM v_product_stock")).one()
            products = s.scalar(select(func.count(Product.id)).where(Product.is_archived == 0))
            customers = s.scalar(select(func.count(Customer.id)).where(Customer.is_archived == 0))
            sq = self._sale_filter(select(func.count(Sale.id), func.coalesce(func.sum(Sale.total_minor), 0))
                                   .where(Sale.status == SaleStatus.COMPLETED), date_from, date_to)
            n_sales, revenue = s.execute(sq).one()
            cogs = s.scalar(self._sale_filter(
                select(func.coalesce(func.sum(LicenseAllocation.quantity * LicenseAllocation.unit_cost_tzs), 0))
                .join(SaleItem, SaleItem.id == LicenseAllocation.sale_item_id).join(Sale, Sale.id == SaleItem.sale_id)
                .where(Sale.status == SaleStatus.COMPLETED), date_from, date_to))
            lq = select(func.coalesce(func.sum(License.purchase_cost_tzs), 0))
            if date_from:
                lq = lq.where(License.purchase_date >= date_from)
            if date_to:
                lq = lq.where(License.purchase_date <= date_to)
            purchase_costs = s.scalar(lq)
        return {
            "total_products": products, "total_keys": stock[0], "available_activations": stock[1],
            "allocated_activations": stock[2], "fully_allocated_keys": stock[3],
            "low_stock": self.ctx.inventory.low_stock_alerts(), "total_customers": customers,
            "total_sales": n_sales, "revenue": revenue, "purchase_costs": purchase_costs,
            "cost_of_sales": cogs, "gross_profit": revenue - cogs,
        }

    def inventory_report(self) -> Report:
        rows = []
        for r in self.ctx.inventory.list_licenses():
            rows.append([r.inventory_ref, r.product_name, r.supplier or "", r.purchase_date,
                         format_money(r.purchase_cost_tzs, with_code=False), r.permitted_capacity,
                         r.allocated_qty, r.remaining_qty, r.stock_state.replace("_", " ").title(),
                         r.expiration_date or ""])
        totals = ["TOTAL", "", "", "", format_money(sum(r.purchase_cost_tzs for r in self.ctx.inventory.list_licenses()),
                                                    with_code=False),
                  sum(r[5] for r in rows), sum(r[6] for r in rows), sum(r[7] for r in rows), "", ""]
        return Report("Inventory report", "All licence keys (costs in TZS)",
                      ["Ref", "Product", "Supplier", "Purchased", "Cost TZS", "Capacity", "Allocated",
                       "Remaining", "State", "Expires"], rows, totals)

    def activation_report(self) -> Report:
        rows = [[r["display_name"], r["total_keys"], r["allocated_activations"], r["available_activations"],
                 r["fully_allocated_keys"], r["low_stock_threshold"],
                 "LOW" if r["available_activations"] < r["low_stock_threshold"] else ""]
                for r in self.ctx.inventory.product_stock()]
        totals = ["TOTAL", sum(r[1] for r in rows), sum(r[2] for r in rows), sum(r[3] for r in rows),
                  sum(r[4] for r in rows), "", ""]
        return Report("Activation balances", "Per product",
                      ["Product", "Keys", "Allocated", "Available", "Fully used keys", "Alert level", "Stock"],
                      rows, totals)

    def sales_report(self, date_from=None, date_to=None) -> Report:
        sales = self.ctx.sales.list_sales(date_from=date_from, date_to=date_to)
        rows = [[x.sales_ref, x.sale_date, x.customer_name, x.product_names, x.quantity,
                 format_money(x.subtotal_minor, with_code=False), format_money(x.discount_minor, with_code=False),
                 format_money(x.total_minor, with_code=False), x.payment_method.replace("_", " ").title(),
                 x.status.title()] for x in sales]
        done = [x for x in sales if x.status == SaleStatus.COMPLETED]
        totals = ["TOTAL (completed)", "", "", "", sum(x.quantity for x in done),
                  format_money(sum(x.subtotal_minor for x in done), with_code=False),
                  format_money(sum(x.discount_minor for x in done), with_code=False),
                  format_money(sum(x.total_minor for x in done), with_code=False), "", ""]
        return Report("Sales report", _period(date_from, date_to),
                      ["Ref", "Date", "Customer", "Product", "Qty", "Subtotal", "Discount", "Total",
                       "Payment", "Status"], rows, totals)

    def customer_report(self, date_from=None, date_to=None) -> Report:
        with self.ctx.db.session() as s:
            q = self._sale_filter(
                select(Customer.customer_ref, Customer.full_name, Customer.organization, Customer.phone,
                       func.count(Sale.id), func.coalesce(func.sum(Sale.total_minor), 0), func.max(Sale.sale_date))
                .join(Sale, Sale.customer_id == Customer.id).where(Sale.status == SaleStatus.COMPLETED)
                .group_by(Customer.id).order_by(func.sum(Sale.total_minor).desc()), date_from, date_to)
            data = s.execute(q).all()
        rows = [[r[0], r[1], r[2] or "", r[3] or "", r[4], format_money(r[5], with_code=False), r[6]] for r in data]
        totals = ["TOTAL", "", "", "", sum(r[4] for r in data), format_money(sum(r[5] for r in data), with_code=False), ""]
        return Report("Customer report", _period(date_from, date_to),
                      ["Ref", "Name", "Organisation", "Phone", "Purchases", "Total spent TZS", "Last purchase"],
                      rows, totals)

    def profit_report(self, date_from=None, date_to=None) -> Report:
        with self.ctx.db.session() as s:
            rev_q = self._sale_filter(
                select(Product.display_name, func.sum(SaleItem.quantity), func.sum(SaleItem.line_total_minor))
                .join(SaleItem, SaleItem.product_id == Product.id).join(Sale, Sale.id == SaleItem.sale_id)
                .where(Sale.status == SaleStatus.COMPLETED).group_by(Product.id), date_from, date_to)
            revenue = {r[0]: (r[1], r[2]) for r in s.execute(rev_q)}
            cost_q = self._sale_filter(
                select(Product.display_name, Sale.status, LicenseAllocation.status,
                       func.sum(LicenseAllocation.quantity * LicenseAllocation.unit_cost_tzs))
                .join(SaleItem, SaleItem.id == LicenseAllocation.sale_item_id).join(Sale, Sale.id == SaleItem.sale_id)
                .join(Product, Product.id == SaleItem.product_id)
                .group_by(Product.id, Sale.status, LicenseAllocation.status), date_from, date_to)
            cost, loss = {}, {}
            for name, sale_status, alloc_status, amount in s.execute(cost_q):
                if sale_status == SaleStatus.COMPLETED:
                    cost[name] = cost.get(name, 0) + amount
                elif alloc_status == AllocationStatus.CONSUMED:
                    loss[name] = loss.get(name, 0) + amount
        names = sorted(set(revenue) | set(cost) | set(loss))
        rows, t = [], [0, 0, 0, 0, 0]
        for n in names:
            units, rev = revenue.get(n, (0, 0))
            c, l = cost.get(n, 0), loss.get(n, 0)
            gp = rev - c - l
            margin = f"{gp / rev * 100:.1f}%" if rev else ""
            rows.append([n, units, format_money(rev, with_code=False), format_money(c, with_code=False),
                         format_money(l, with_code=False), format_money(gp, with_code=False), margin])
            for i, v in enumerate((units, rev, c, l, gp)):
                t[i] += v
        totals = ["TOTAL", t[0], format_money(t[1], with_code=False), format_money(t[2], with_code=False),
                  format_money(t[3], with_code=False), format_money(t[4], with_code=False),
                  f"{t[4] / t[1] * 100:.1f}%" if t[1] else ""]
        return Report("Profit report", _period(date_from, date_to) + " · TZS",
                      ["Product", "Units", "Revenue", "Cost of keys sold", "Cancelled & consumed",
                       "Gross profit", "Margin"], rows, totals)

    def report(self, name: str, date_from=None, date_to=None) -> Report:
        return {
            "inventory": lambda: self.inventory_report(),
            "sales": lambda: self.sales_report(date_from, date_to),
            "customers": lambda: self.customer_report(date_from, date_to),
            "activations": lambda: self.activation_report(),
            "profit": lambda: self.profit_report(date_from, date_to),
        }[name]()
