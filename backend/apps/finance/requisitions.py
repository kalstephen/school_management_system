"""The requisition journey.

1. Any staff member asks (what, why, how much).
2. It climbs the ranks above them: their head of department (when a department is named), the
   Director of Studies, the head teacher, and the director when the amount is above the head
   teacher's approval limit. Steps at or below the requester's own rank, and roles nobody
   holds, are skipped. A higher academic role may act for a missing or absent lower one.
3. Finance (the bursar, or the director) sees it last and issues the money.
4. The requester accounts for it: what was spent, change returned, receipts. Finance confirms
   and the expense is corrected to what was actually spent.
Each person is notified when it is their turn.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import ROLE_RANK
from apps.core.exceptions import BusinessRuleError

from .models import Approval, Expense, FinanceSettings, Requisition

STEPS = {
    "hod": "Head of department",
    "dos": "Director of Studies",
    "head_teacher": "Head teacher",
    "director": "Director",
    "finance": "Finance (issues the money)",
}
CHAIN = ["hod", "dos", "head_teacher", "director"]


def _holders(school, role, department_id=None):
    from apps.accounts.models import RoleAssignment

    rows = RoleAssignment.objects.filter(school=school, role=role, membership__is_active=True)
    if role == "hod":
        rows = rows.filter(scope_type="department", scope_id=department_id)
    return [r.membership.user for r in rows.select_related("membership__user")]


def build_route(requisition, requester):
    from apps.accounts.services import rank_of

    school = requisition.school
    rank = rank_of(requester, school)
    steps = []
    needed = FinanceSettings.for_school(school).level_for(requisition.estimated_amount)
    for role in CHAIN:
        if ROLE_RANK[role] <= rank:
            continue
        if role == "hod" and not (
            requisition.department_id and _holders(school, "hod", requisition.department_id)
        ):
            continue
        if role == "director" and needed < 3 and steps:
            continue
        if role != "hod" and not _holders(school, role):
            continue
        steps.append(role)
    return steps + ["finance"]


def users_for_step(requisition, step):
    """Who is asked to act at this step (notified); others may still act if allowed."""
    if step == "finance":
        from apps.accounts.models import RoleAssignment

        roles = RoleAssignment.objects.filter(
            school=requisition.school, role="bursar", membership__is_active=True
        )
        users = [r.membership.user for r in roles.select_related("membership__user")]
        return users or _holders(requisition.school, "director")
    return _holders(requisition.school, step, requisition.department_id)


def can_act(user, requisition):
    """May this user decide the requisition's current step?"""
    from apps.accounts.services import effective_perms, user_roles

    if requisition.status not in (Requisition.Status.PENDING, Requisition.Status.APPROVED):
        return False
    step = current_step(requisition)
    if step is None or user.pk == requisition.created_by_id:
        return False
    school = requisition.school
    if step == "finance":
        return "finance.manage" in effective_perms(user, school)
    for role in user_roles(user, school):
        if role.role not in CHAIN or ROLE_RANK[role.role] < ROLE_RANK[step]:
            continue
        if role.role == "hod" and step == "hod" and role.scope_id != requisition.department_id:
            continue
        return True
    return False


def current_step(requisition):
    route = requisition.route or []
    return route[requisition.step] if requisition.step < len(route) else None


def _notify(requisition, users, title, body=""):
    from apps.communication.services import notify

    notify(requisition.school, [u for u in users if u], title, body, link="/finance/requisitions")


def submit(requisition, requester):
    requisition.route = build_route(requisition, requester)
    requisition.step = 0
    requisition.status = (
        Requisition.Status.APPROVED if requisition.route == ["finance"] else Requisition.Status.PENDING
    )
    requisition.save()
    step = current_step(requisition)
    _notify(
        requisition,
        users_for_step(requisition, step),
        f"Requisition to {'issue' if step == 'finance' else 'approve'}: {requisition.title}",
        f"From {requester.display_name}, UGX {requisition.estimated_amount:,.0f}.",
    )
    return requisition


def approve(requisition, user, comment=""):
    if not can_act(user, requisition) or current_step(requisition) == "finance":
        raise BusinessRuleError({"detail": "This requisition is not waiting for you."})
    from apps.accounts.services import approval_level

    with transaction.atomic():
        Approval.objects.create(
            school=requisition.school,
            requisition=requisition,
            user=user,
            level=approval_level(user, requisition.school),
            step=current_step(requisition),
            decision=Approval.Decision.APPROVED,
            comment=comment[:300],
        )
        requisition.step += 1
        requisition.decided_by = user
        if current_step(requisition) == "finance":
            requisition.status = Requisition.Status.APPROVED
        requisition.save()
    step = current_step(requisition)
    _notify(
        requisition,
        users_for_step(requisition, step),
        f"Requisition to {'issue' if step == 'finance' else 'approve'}: {requisition.title}",
        f"Approved by {user.display_name}.",
    )
    return requisition


def reject(requisition, user, comment):
    if not can_act(user, requisition):
        raise BusinessRuleError({"detail": "This requisition is not waiting for you."})
    if not comment:
        raise BusinessRuleError({"comment": "Say why, so the requester knows."})
    from apps.accounts.services import approval_level

    Approval.objects.create(
        school=requisition.school,
        requisition=requisition,
        user=user,
        level=approval_level(user, requisition.school),
        step=current_step(requisition) or "",
        decision=Approval.Decision.REJECTED,
        comment=comment[:300],
    )
    requisition.status, requisition.decided_by, requisition.decision_comment = (
        Requisition.Status.REJECTED,
        user,
        comment[:300],
    )
    requisition.save()
    _notify(requisition, [requisition.created_by], f"Requisition not approved: {requisition.title}", comment)
    return requisition


def disburse(requisition, user, amount, method, category, sub_category=None):
    """Finance issues the money; it is recorded as an expense at once."""
    from . import services

    if requisition.status != Requisition.Status.APPROVED or not can_act(user, requisition):
        raise BusinessRuleError({"detail": "Only finance can issue money for an approved requisition."})
    if not amount or amount <= 0:
        raise BusinessRuleError({"amount": "Give the amount issued."})
    with transaction.atomic():
        expense = Expense.objects.create(
            school=requisition.school,
            date=timezone.localdate(),
            category=category,
            sub_category=sub_category,
            description=f"Requisition: {requisition.title}"[:300],
            amount=amount,
            method=method or "cash",
            payee=requisition.created_by.display_name if requisition.created_by else "",
            department=requisition.department,
            requisition=requisition,
            status=Expense.Status.APPROVED,
            required_level=FinanceSettings.for_school(requisition.school).level_for(amount),
        )
        services.after_spend(expense)
        requisition.status = Requisition.Status.DISBURSED
        requisition.disbursed_amount, requisition.disbursement_method = amount, method or "cash"
        requisition.disbursed_by, requisition.disbursed_at = user, timezone.now()
        requisition.step = len(requisition.route)
        requisition.save()
    _notify(
        requisition,
        [requisition.created_by],
        f"Money issued: {requisition.title}",
        f"UGX {amount:,.0f}. Please account for it (what you spent and any change) with receipts.",
    )
    return requisition


def account(requisition, user, spent, returned, note, receipt=None):
    """The requester (or finance on their behalf) reports how the money was used."""
    from apps.accounts.services import effective_perms

    if requisition.status != Requisition.Status.DISBURSED:
        raise BusinessRuleError({"detail": "Only issued money is accounted for."})
    if user.pk != requisition.created_by_id and "finance.manage" not in effective_perms(
        user, requisition.school
    ):
        raise BusinessRuleError({"detail": "The person who asked for the money accounts for it."})
    if spent is None or spent < 0 or (returned or 0) < 0:
        raise BusinessRuleError({"spent_amount": "Give what was spent (and any change returned)."})
    if spent + (returned or 0) != requisition.disbursed_amount and not note:
        raise BusinessRuleError(
            {"accountability_note": "Spent plus change differs from the money issued; explain why."}
        )
    requisition.spent_amount, requisition.returned_amount = spent, returned or 0
    requisition.accountability_note = note or ""
    if receipt:
        requisition.receipt = receipt
    requisition.accounted_submitted_at = timezone.now()
    requisition.save()
    _notify(
        requisition,
        users_for_step(requisition, "finance"),
        f"Accountability to check: {requisition.title}",
        f"Spent UGX {spent:,.0f}, returned UGX {(returned or 0):,.0f}.",
    )
    return requisition


def confirm_accountability(requisition, user):
    from apps.accounts.services import effective_perms

    if "finance.manage" not in effective_perms(user, requisition.school):
        raise BusinessRuleError({"detail": "Finance confirms accountability."})
    if requisition.status != Requisition.Status.DISBURSED or requisition.accounted_submitted_at is None:
        raise BusinessRuleError({"detail": "The requester has not accounted for this money yet."})
    with transaction.atomic():
        # The expense becomes what was really spent; change returned goes back to the school.
        requisition.expenses.update(amount=requisition.spent_amount)
        requisition.status, requisition.accounted_confirmed_by = Requisition.Status.ACCOUNTED, user
        requisition.accounted_at = timezone.now()
        requisition.save()
    _notify(requisition, [requisition.created_by], f"Accountability accepted: {requisition.title}")
    return requisition
