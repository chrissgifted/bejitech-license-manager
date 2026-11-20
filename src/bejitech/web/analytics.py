"""Figures for the dashboard: trends, top products and customers, money collected and owed, stock."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select

from bejitech.core.enums import EntryKind, SaleStatus
from bejitech.db.models import CustomerEntry

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _previous_range(date_from: str | None, date_to: str | None) -> tuple[str | None, str | None]:
    """The period of the same length just before [date_from, date_to]."""
    if not date_from or not date_to:
        return None, None
    a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    days = (b - a).days + 1
    return date.fromordinal(a.toordinal() - days).isoformat(), date.fromordinal(a.toordinal() - 1).isoformat()


def _in(d: str, lo: str | None, hi: str | None) -> bool:
    return (not lo or d >= lo) and (not hi or d <= hi)


def _change(now: int, before: int | None) -> float | None:
    if before is None or before == 0:
        return None
    return (now - before) / abs(before) * 100


def build(ctx, date_from: str | None, date_to: str | None) -> dict:
    sales = [s for s in ctx.sales.list_sales() if s.status == SaleStatus.COMPLETED]

    def cost(s) -> int:
        return sum(a.unit_cost_tzs * a.quantity for a in s.allocations)

    period = [s for s in sales if _in(s.sale_date, date_from, date_to)]
    p_from, p_to = _previous_range(date_from, date_to)
    prev = [s for s in sales if p_from and _in(s.sale_date, p_from, p_to)]

    revenue = sum(s.total_minor for s in period)
    profit = revenue - sum(cost(s) for s in period)
    prev_revenue = sum(s.total_minor for s in prev) if p_from else None
    prev_profit = (prev_revenue - sum(cost(s) for s in prev)) if p_from else None

    with ctx.db.session() as db:
        q = select(func.coalesce(func.sum(CustomerEntry.amount_minor), 0)).where(
            CustomerEntry.kind == EntryKind.PAYMENT, CustomerEntry.is_void == 0)
        if date_from:
            q = q.where(CustomerEntry.entry_date >= date_from)
        if date_to:
            q = q.where(CustomerEntry.entry_date <= date_to)
        collected = int(db.scalar(q) or 0)

    balances = ctx.accounts.balances()
    owed = sum(b for b in balances.values() if b > 0)

    # Last 12 months (always, whatever the period filter) for the trend chart
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    months.reverse()
    by_month = defaultdict(lambda: [0, 0, 0])  # revenue, profit, count
    for s in sales:
        key = (int(s.sale_date[:4]), int(s.sale_date[5:7]))
        by_month[key][0] += s.total_minor
        by_month[key][1] += s.total_minor - cost(s)
        by_month[key][2] += 1
    trend = [{"label": MONTHS[mm - 1], "year": yy, "revenue": by_month[(yy, mm)][0],
              "profit": by_month[(yy, mm)][1], "count": by_month[(yy, mm)][2],
              "current": (yy, mm) == (today.year, today.month)} for yy, mm in months]
    top = max([t["revenue"] for t in trend] + [1])
    for t in trend:
        t["pct"] = round(t["revenue"] / top * 100, 1)

    # Top products and customers in the period
    prod = defaultdict(lambda: [0, 0])
    cust = defaultdict(lambda: [0, 0, ""])
    for s in period:
        prod[s.product_names][0] += s.total_minor
        prod[s.product_names][1] += s.quantity
        c = cust[s.customer_id]
        c[0] += s.total_minor
        c[1] += 1
        c[2] = s.customer_name
    top_products = sorted(({"name": k, "revenue": v[0], "units": v[1]} for k, v in prod.items()),
                          key=lambda x: -x["revenue"])[:6]
    pmax = max([x["revenue"] for x in top_products] + [1])
    for x in top_products:
        x["pct"] = round(x["revenue"] / pmax * 100, 1)
        x["share"] = round(x["revenue"] / revenue * 100) if revenue else 0
    top_customers = sorted(({"id": k, "name": v[2], "revenue": v[0], "sales": v[1],
                             "balance": balances.get(k, 0)} for k, v in cust.items()),
                           key=lambda x: -x["revenue"])[:5]

    # Money: collected vs still owed (all time)
    total_paid_ever = 0
    with ctx.db.session() as db:
        total_paid_ever = int(db.scalar(select(func.coalesce(func.sum(CustomerEntry.amount_minor), 0)).where(
            CustomerEntry.kind == EntryKind.PAYMENT, CustomerEntry.is_void == 0)) or 0)
    billed = total_paid_ever + owed
    collection = {"paid": total_paid_ever, "owed": owed,
                  "paid_pct": round(total_paid_ever / billed * 100) if billed else 100}

    # Stock by product
    stock = []
    for p in ctx.catalogue.list_products():
        stock.append({"id": p.id, "name": p.display_name, "available": p.available_activations,
                      "key_count": p.total_keys, "low": p.available_activations < (p.low_stock_threshold or 0)})
    smax = max([x["available"] for x in stock] + [1])
    for x in stock:
        x["pct"] = round(x["available"] / smax * 100, 1)
    stock.sort(key=lambda x: x["available"])

    return {
        "revenue": revenue, "revenue_change": _change(revenue, prev_revenue),
        "profit": profit, "profit_change": _change(profit, prev_profit),
        "margin": round(profit / revenue * 100) if revenue else None,
        "sales": len(period), "sales_change": _change(len(period), len(prev) if p_from else None),
        "avg_sale": revenue // len(period) if period else 0,
        "collected": collected, "owed": owed, "debtors": sum(1 for b in balances.values() if b > 0),
        "trend": trend, "trend_total": sum(t["revenue"] for t in trend),
        "top_products": top_products, "top_customers": top_customers,
        "collection": collection, "stock": stock, "has_compare": bool(p_from),
    }
