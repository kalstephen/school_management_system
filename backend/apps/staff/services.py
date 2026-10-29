from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import Membership, RoleAssignment, User
from apps.accounts.roles import ROLE_LABELS
from apps.accounts.services import can_assign, rank_of
from apps.core.exceptions import BusinessRuleError


def create_staff_login(request, staff, login_username, login_password, login_role="subject_teacher"):
    """Create (or link) the sign-in for a new staff member: user, school membership and role.

    The person entering the teacher may only give roles below their own level."""
    role = login_role or "subject_teacher"
    if role not in ROLE_LABELS:
        raise BusinessRuleError({"login_role": "Unknown role."})
    if not can_assign(rank_of(request.user, request.school), role):
        raise BusinessRuleError({"login_role": f"You cannot give the {ROLE_LABELS[role]} role."})
    with transaction.atomic():
        user = User.objects.filter(username__iexact=login_username).first()
        if user is None:
            if not login_password:
                raise BusinessRuleError({"login_password": "Give a password for the new sign-in."})
            try:
                validate_password(login_password)
            except ValidationError as exc:
                raise BusinessRuleError({"login_password": exc.messages})
            user = User(
                username=login_username,
                first_name=staff.first_name,
                last_name=staff.last_name,
                email=staff.email,
                phone=staff.phone,
            )
            user.set_password(login_password)
            user.save()
        membership, _ = Membership.objects.get_or_create(
            school=request.school, user=user, defaults={"title": staff.designation}
        )
        RoleAssignment.objects.get_or_create(
            school=request.school, membership=membership, role=role, scope_type="school", scope_id=None
        )
    return user
