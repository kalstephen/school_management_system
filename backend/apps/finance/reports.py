"""Finance reports. Every report returns plain rows so it can be shown on screen or
exported to Excel/PDF for the board and auditors."""

import datetime
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Sum

from apps.learners.models import Enrolment

from .models import Budget, Expense, OtherIncome, PettyCashEntry, SupplierBill

SPENT = Expense.SPENT


def _num(value):
    return float(value or 0)


def spent(school):
    return Expense.objects.filter(school=school, status__in=SPENT)


def daily_sheet(school, date):
    rows = spent(school).filter(date=date).select_related("category", "sub_category", "supplier")
    items = [
        {
            "id": e.id,
            "description": e.description,
            "category": e.category.name,
            "sub_category": e.sub_category.name if e.sub_category else "",
            "payee": e.payee or (e.supplier.name if e.supplier else ""),
            "method": e.get_method_display(),
            "reference": e.reference,
            "amount": _num(e.amount),
        }
        for e in rows
    ]
    by_method = defaultdict(float)
    for e in items:
        by_method[e["method"]] += e["amount"]
    return {"date": date, "items": items, "total": sum(i["amount"] for i in items), "by_method": by_method}


def weekly_summary(school, start):
    end = start + datetime.timedelta(days=6)
    rows = (
        spent(school)
        .filter(date__range=(start, end))
        .values("date", "category__name")
        .annotate(total=Sum("amount"))
    )
    table = defaultdict(lambda: defaultdict(float))
    for r in rows:
        table[r["category__name"]][str(r["date"])] += _num(r["total"])
    days = [str(start + datetime.timedelta(days=i)) for i in range(7)]
    return {
        "start": start,
        "end": end,
        "days": days,
        "rows": [
            {"category": c, **{d: v.get(d, 0) for d in days}, "total": sum(v.values())}
            for c, v in sorted(table.items())
        ],
        "total": sum(sum(v.values()) for v in table.values()),
    }


def termly_statement(school, term):
    rows = (
        spent(school)
        .filter(term=term)
        .values("category__name", "sub_category__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("category__name", "sub_category__name")
    )
    categories = defaultdict(lambda: {"total": 0.0, "sub_categories": []})
    for r in rows:
        cat = categories[r["category__name"]]
        cat["total"] += _num(r["total"])
        cat["sub_categories"].append(
            {"name": r["sub_category__name"] or "General", "total": _num(r["total"]), "count": r["count"]}
        )
    total = sum(c["total"] for c in categories.values())
    income = _num(OtherIncome.objects.filter(school=school, term=term).aggregate(t=Sum("amount"))["t"])
    learners = Enrolment.objects.filter(term=term).count()
    return {
        "term": str(term),
        "categories": [
            {"category": k, **v} for k, v in sorted(categories.items(), key=lambda kv: -kv[1]["total"])
        ],
        "total": total,
        "other_income": income,
        "net_cash_position": income - total,
        "learners": learners,
        "cost_per_learner": round(total / learners) if learners else None,
    }


def budget_vs_actual(school, term):
    budget = Budget.objects.filter(school=school, term=term).prefetch_related("lines__category").first()
    actual = {
        r["category_id"]: _num(r["total"])
        for r in spent(school).filter(term=term).values("category_id").annotate(total=Sum("amount"))
    }
    lines = []
    for line in budget.lines.all() if budget else []:
        used = actual.pop(line.category_id, 0.0)
        pct = round(used / _num(line.amount) * 100, 1) if line.amount else None
        status = (
            "over"
            if pct is not None and pct >= 100
            else ("warning" if pct is not None and pct >= 80 else "ok")
        )
        lines.append(
            {
                "category_id": line.category_id,
                "category": line.category.name,
                "budget": _num(line.amount),
                "actual": used,
                "remaining": _num(line.amount) - used,
                "percent": pct,
                "status": status,
            }
        )
    from .models import ExpenseCategory

    names = dict(ExpenseCategory.objects.filter(pk__in=actual).values_list("id", "name"))
    for category_id, used in actual.items():
        lines.append(
            {
                "category_id": category_id,
                "category": names.get(category_id, "?"),
                "budget": 0.0,
                "actual": used,
                "remaining": -used,
                "percent": None,
                "status": "unbudgeted",
            }
        )
    weeks = []
    start = term.start_date
    cumulative = 0.0
    last_week = min(term.end_date, datetime.date.today())  # no empty future weeks
    while start <= last_week:
        end = start + datetime.timedelta(days=6)
        week_total = _num(
            spent(school).filter(term=term, date__range=(start, end)).aggregate(t=Sum("amount"))["t"]
        )
        cumulative += week_total
        weeks.append({"week_start": start, "spent": week_total, "cumulative": cumulative})
        start = end + datetime.timedelta(days=1)
    return {
        "term": str(term),
        "lines": lines,
        "weeks": weeks,
        "budget_total": sum(line["budget"] for line in lines),
        "actual_total": sum(line["actual"] for line in lines),
    }


def petty_cash_book(petty_float, start=None, end=None):
    entries = PettyCashEntry.objects.filter(float=petty_float).order_by("date", "id")
    opening = Decimal(0)
    if start:
        before = entries.filter(date__lt=start)
        opening = sum((e.amount if e.kind == "topup" else -e.amount) for e in before)
        entries = entries.filter(date__gte=start)
    if end:
        entries = entries.filter(date__lte=end)
    balance = opening
    rows = []
    for e in entries:
        balance += e.amount if e.kind == "topup" else -e.amount
        rows.append(
            {
                "date": e.date,
                "description": e.description,
                "in": _num(e.amount) if e.kind == "topup" else 0,
                "out": _num(e.amount) if e.kind == "spend" else 0,
                "balance": _num(balance),
            }
        )
    return {"float": petty_float.name, "opening": _num(opening), "rows": rows, "closing": _num(balance)}


def supplier_statement(supplier):
    rows = []
    for bill in SupplierBill.objects.filter(supplier=supplier).prefetch_related("payments").order_by("date"):
        rows.append(
            {
                "date": bill.date,
                "type": "Bill",
                "reference": bill.reference,
                "description": bill.description,
                "debit": 0,
                "credit": _num(bill.amount),
            }
        )
        for p in bill.payments.all():
            rows.append(
                {
                    "date": p.date,
                    "type": "Payment",
                    "reference": p.reference,
                    "description": bill.description,
                    "debit": _num(p.amount),
                    "credit": 0,
                }
            )
    rows.sort(key=lambda r: r["date"])
    balance = 0.0
    for r in rows:
        balance += r["credit"] - r["debit"]
        r["balance"] = balance
    return {"supplier": supplier.name, "rows": rows, "amount_owed": balance}


def top_cost_items(school, term, limit=10):
    rows = (
        spent(school)
        .filter(term=term)
        .values("category__name", "sub_category__name", "description")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")[:limit]
    )
    return [
        {
            "item": r["sub_category__name"] or r["description"],
            "category": r["category__name"],
            "total": _num(r["total"]),
            "count": r["count"],
        }
        for r in rows
    ]


def same_term_last_year(school, term):
    from apps.schoolsetup.models import Term

    previous = (
        Term.objects.filter(
            school=school, number=term.number, academic_year__start_date__lt=term.academic_year.start_date
        )
        .order_by("-academic_year__start_date")
        .first()
    )
    current = {
        r["category__name"]: _num(r["total"])
        for r in spent(school).filter(term=term).values("category__name").annotate(total=Sum("amount"))
    }
    before = {}
    if previous:
        before = {
            r["category__name"]: _num(r["total"])
            for r in spent(school)
            .filter(term=previous)
            .values("category__name")
            .annotate(total=Sum("amount"))
        }
    rows = []
    for name in sorted(set(current) | set(before)):
        now, then = current.get(name, 0.0), before.get(name, 0.0)
        rows.append(
            {
                "category": name,
                "this_term": now,
                "last_year": then,
                "change_percent": round((now - then) / then * 100, 1) if then else None,
            }
        )
    return {"term": str(term), "compared_with": str(previous) if previous else None, "rows": rows}


def outstanding_bills(school):
    bills = (
        SupplierBill.objects.filter(school=school)
        .exclude(status=SupplierBill.Status.PAID)
        .select_related("supplier")
    )
    return [
        {
            "id": b.id,
            "supplier": b.supplier.name,
            "description": b.description,
            "due_date": b.due_date,
            "amount": _num(b.amount),
            "balance": _num(b.balance),
        }
        for b in bills
    ]
