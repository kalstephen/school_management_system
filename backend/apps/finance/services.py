import calendar
import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.services import approval_level
from apps.core.exceptions import BusinessRuleError
from apps.core.modules import module_enabled

from .models import (
    Approval,
    BudgetLine,
    Expense,
    FinanceSettings,
    PettyCashEntry,
    RecurringExpense,
    SupplierBill,
    SupplierPayment,
)

E = Expense.Status
LEVEL_NAMES = {1: "the bursar", 2: "the head teacher", 3: "the director"}


def submit_expense(expense, user):
    """Send an expense for approval. If the person entering it may approve that amount
    (e.g. the bursar, below the bursar limit) it is approved straight away."""
    if expense.status not in (E.DRAFT, E.REJECTED):
        raise BusinessRuleError({"detail": "Only draft or rejected expenses can be submitted."})
    settings = FinanceSettings.for_school(expense.school)
    expense.required_level = settings.level_for(expense.amount)
    expense.status = E.PENDING
    expense.save()
    if approval_level(user, expense.school) >= expense.required_level:
        Approval.objects.create(
            school=expense.school,
            expense=expense,
            user=user,
            level=expense.required_level,
            decision=Approval.Decision.AUTO,
        )
        _mark_approved(expense)
    return expense


def _mark_approved(expense):
    expense.status = E.APPROVED
    expense.save()
    after_spend(expense)


def approve_expense(expense, user, comment=""):
    if expense.status != E.PENDING:
        raise BusinessRuleError({"detail": "Only expenses awaiting approval can be approved."})
    level = approval_level(user, expense.school)
    if level < expense.required_level:
        raise BusinessRuleError(
            {"detail": f"This amount needs approval by {LEVEL_NAMES[expense.required_level]}."}
        )
    if expense.created_by_id == user.id and level < 3 and expense.required_level > 1:
        raise BusinessRuleError({"detail": "You cannot approve an expense you entered yourself."})
    Approval.objects.create(
        school=expense.school,
        expense=expense,
        user=user,
        level=level,
        decision=Approval.Decision.APPROVED,
        comment=comment,
    )
    _mark_approved(expense)
    return expense


def reject_expense(expense, user, comment):
    if expense.status != E.PENDING:
        raise BusinessRuleError({"detail": "Only expenses awaiting approval can be rejected."})
    if not comment:
        raise BusinessRuleError({"comment": "Give a reason for rejecting."})
    if approval_level(user, expense.school) < 1:
        raise BusinessRuleError({"detail": "You cannot approve or reject expenses."})
    Approval.objects.create(
        school=expense.school,
        expense=expense,
        user=user,
        level=approval_level(user, expense.school),
        decision=Approval.Decision.REJECTED,
        comment=comment,
    )
    expense.status = E.REJECTED
    expense.save()
    return expense


def mark_paid(expense, paid_on=None, method=None, reference=None):
    if expense.status != E.APPROVED:
        raise BusinessRuleError({"detail": "Only approved expenses can be marked as paid."})
    expense.status = E.PAID
    expense.paid_on = paid_on or timezone.localdate()
    if method:
        expense.method = method
    if reference:
        expense.reference = reference
    expense.save()
    return expense


def after_spend(expense):
    """Side effects once money is committed: budget alerts and the asset register."""
    check_budget_alerts(expense)
    if expense.category.is_capital and module_enabled(expense.school, "stores"):
        from apps.stores.models import Asset

        if not Asset.objects.filter(school=expense.school, expense=expense).exists():
            Asset.objects.create(
                school=expense.school,
                name=expense.description[:200],
                purchase_date=expense.date,
                purchase_cost=expense.amount,
                supplier=expense.supplier.name if expense.supplier else expense.payee,
                expense=expense,
            )


def category_spend(school, term, category):
    return Expense.objects.filter(
        school=school, term=term, category=category, status__in=Expense.SPENT
    ).aggregate(total=Sum("amount"))["total"] or Decimal(0)


def check_budget_alerts(expense):
    from apps.accounts.models import Membership
    from apps.communication.services import notify

    if expense.term_id is None:
        return
    line = BudgetLine.objects.filter(budget__term=expense.term, category=expense.category).first()
    if line is None or not line.amount:
        return
    spent = category_spend(expense.school, expense.term, expense.category)
    pct = spent / line.amount * 100
    message = None
    if pct >= 100 and not line.alerted_100:
        line.alerted_100 = line.alerted_80 = True
        message = f"{expense.category} has reached {pct:.0f}% of its budget for {expense.term}."
    elif pct >= 80 and not line.alerted_80:
        line.alerted_80 = True
        message = f"{expense.category} has used {pct:.0f}% of its budget for {expense.term}."
    if message:
        line.save()
        users = [
            m.user
            for m in Membership.objects.filter(
                school=expense.school, is_active=True, roles__role__in=["bursar", "head_teacher", "director"]
            )
            .distinct()
            .select_related("user")
        ]
        notify(expense.school, users, "Budget alert", message, link="/finance/budgets")


def spend_petty_cash(petty_float, user, date, amount, description, category, sub_category=None, payee=""):
    """Record spending from a float: an entry on the float and a paid cash expense."""
    amount = Decimal(str(amount))
    if amount <= 0:
        raise BusinessRuleError({"amount": "The amount must be more than zero."})
    if amount > petty_float.balance:
        raise BusinessRuleError({"amount": f"The float only has UGX {petty_float.balance:,.0f}."})
    with transaction.atomic():
        expense = Expense.objects.create(
            school=petty_float.school,
            date=date,
            category=category,
            sub_category=sub_category,
            description=description,
            amount=amount,
            method="cash",
            payee=payee,
            status=E.PAID,
            paid_on=date,
            project=f"Petty cash: {petty_float.name}",
        )
        entry = PettyCashEntry.objects.create(
            school=petty_float.school,
            float=petty_float,
            date=date,
            kind="spend",
            amount=amount,
            description=description,
            expense=expense,
        )
        after_spend(expense)
    return entry


def needs_replenishment(petty_float):
    return petty_float.balance < petty_float.replenish_below


def pay_bill(bill, date, amount, method, reference=""):
    amount = Decimal(str(amount))
    if amount <= 0 or amount > bill.balance:
        raise BusinessRuleError({"amount": f"Pay between 1 and the balance of UGX {bill.balance:,.0f}."})
    with transaction.atomic():
        expense = Expense.objects.create(
            school=bill.school,
            date=date,
            category=bill.category,
            description=f"{bill.supplier}: {bill.description}"[:300],
            amount=amount,
            method=method,
            supplier=bill.supplier,
            payee=bill.supplier.name,
            reference=reference,
            status=E.PAID,
            paid_on=date,
        )
        payment = SupplierPayment.objects.create(
            school=bill.school,
            bill=bill,
            date=date,
            amount=amount,
            method=method,
            reference=reference,
            expense=expense,
        )
        bill.status = SupplierBill.Status.PAID if bill.balance <= 0 else SupplierBill.Status.PART_PAID
        bill.save()
        after_spend(expense)
    return payment


def _add_month(day):
    month = day.month % 12 + 1
    year = day.year + (day.month == 12)
    return datetime.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def generate_recurring(school, today=None):
    """Create pending expenses for recurring items that are due (rent, Yaka, internet, salary totals)."""
    from apps.schoolsetup.models import Term

    today = today or timezone.localdate()
    created = 0
    for item in RecurringExpense.objects.filter(school=school, is_active=True, next_date__lte=today):
        while item.next_date <= today:
            Expense.objects.create(
                school=school,
                date=item.next_date,
                category=item.category,
                sub_category=item.sub_category,
                description=item.description,
                amount=item.amount,
                method=item.method,
                payee=item.payee,
                supplier=item.supplier,
                status=E.PENDING,
                required_level=FinanceSettings.for_school(school).level_for(item.amount),
                recurring=item,
            )
            created += 1
            if item.frequency == RecurringExpense.Frequency.MONTHLY:
                item.next_date = _add_month(item.next_date)
            else:
                next_term = (
                    Term.objects.filter(school=school, start_date__gt=item.next_date)
                    .order_by("start_date")
                    .first()
                )
                if next_term is None:
                    item.is_active = False
                    break
                item.next_date = next_term.start_date
        item.save()
    return created


def copy_budget_forward(budget, from_budget):
    created = 0
    for line in from_budget.lines.all():
        _, made = BudgetLine.objects.get_or_create(
            school=budget.school, budget=budget, category=line.category, defaults={"amount": line.amount}
        )
        created += int(made)
    return created


def receive_delivery(delivery):
    """When Stores is on, delivered items go into stock."""
    if not module_enabled(delivery.school, "stores"):
        return 0
    from apps.stores.models import Item, StockMovement

    moved = 0
    for line in delivery.items:
        item = Item.objects.filter(school=delivery.school, pk=line.get("stock_item")).first()
        if item and line.get("qty"):
            StockMovement.objects.create(
                school=delivery.school,
                item=item,
                store=item.store,
                kind="in",
                quantity=line["qty"],
                date=delivery.date,
                reference=f"PO {delivery.purchase_order.number}",
                notes=f"Delivery from {delivery.purchase_order.supplier}",
            )
            moved += 1
    return moved
