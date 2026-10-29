from django.utils import timezone

from .roles import (
    APPROVAL_LEVELS,
    MEMBER_BASE,
    ROLE_PERMS,
    ROLE_RANK,
    SCHOOL_WIDE_ROLES,
    TOP_SCHOOL_RANK,
    VIEW_ALL,
)

SCHOOL_SESSION_KEY = "school_id"
# Which door the person came in by: "school" (school portal, School ID + username) or
# "platform" (platform console). Platform rights exist only in a platform session, so a
# school sign-in never carries them, even for someone who is also on the platform team.
PORTAL_SESSION_KEY = "portal"
PLATFORM_PORTAL = "platform"
SCHOOL_PORTAL = "school"


def is_platform_account(user):
    return bool(user and user.is_authenticated and (user.is_platform_admin or user.is_superuser))


def platform_session(request):
    """True only for a platform-team account that signed in through the platform console."""
    return is_platform_account(request.user) and request.session.get(PORTAL_SESSION_KEY) == PLATFORM_PORTAL


def _in_platform_session(user):
    from apps.core.context import get_platform_session

    return is_platform_account(user) and get_platform_session()


def active_memberships(user):
    from .models import Membership

    return Membership.objects.filter(user=user, is_active=True, school__is_active=True).select_related(
        "school"
    )


def resolve_school(request, user):
    """The school this request acts on.

    School portal: the school chosen at sign-in (School ID), else the user's first school.
    Platform console: no school, unless the team opens one that granted support access."""
    from apps.core.models import School

    wanted = request.headers.get("X-School-Id") or request.session.get(SCHOOL_SESSION_KEY)
    if wanted:
        try:
            wanted = int(wanted)
        except (TypeError, ValueError):
            wanted = None
    if platform_session(request):
        if wanted and has_support_access(wanted):
            return School.objects.filter(pk=wanted).first()
        return None
    memberships = active_memberships(user)
    if wanted:
        membership = memberships.filter(school_id=wanted).first()
        if membership:
            return membership.school
    first = memberships.first()
    return first.school if first else None


def has_support_access(school_id):
    from apps.subscriptions.models import SupportAccessGrant

    return SupportAccessGrant.objects.filter(school_id=school_id, expires_at__gt=timezone.now()).exists()


def user_roles(user, school):
    from .models import RoleAssignment

    if school is None or not user.is_authenticated:
        return RoleAssignment.objects.none()
    return RoleAssignment.objects.filter(membership__user=user, membership__is_active=True, school=school)


def effective_perms(user, school):
    """Every permission the user has in this school: roles plus unexpired grants.
    Platform admins with support access get read-only access only."""
    from .models import Membership, PermissionGrant

    if school is None or not user.is_authenticated:
        return frozenset()
    perms = set()
    if Membership.objects.filter(user=user, school=school, is_active=True).exists():
        perms |= MEMBER_BASE
    for role in user_roles(user, school).values_list("role", flat=True):
        perms |= ROLE_PERMS.get(role, set())
    perms |= set(
        PermissionGrant.objects.filter(
            membership__user=user, school=school, expires_at__gt=timezone.now()
        ).values_list("permission", flat=True)
    )
    if not perms and _in_platform_session(user) and has_support_access(school.pk):
        perms = set(VIEW_ALL)
    return frozenset(perms)


def rank_of(user, school):
    """The user's authority over accounts in this school: their highest role's rank.
    The platform team ranks above every school role, but only in a platform session."""
    if _in_platform_session(user):
        return TOP_SCHOOL_RANK + 1
    roles = user_roles(user, school).values_list("role", flat=True)
    return max([ROLE_RANK.get(r, 0) for r in roles] or [0])


def membership_rank(membership):
    roles = membership.roles.values_list("role", flat=True)
    return max([ROLE_RANK.get(r, 0) for r in roles] or [0])


def can_assign(actor_rank, role):
    """You may hand out roles ranked below yours; the director may also appoint a director."""
    target = ROLE_RANK.get(role, 0)
    return target < actor_rank or (actor_rank >= TOP_SCHOOL_RANK and target <= TOP_SCHOOL_RANK)


def can_manage(actor_rank, membership):
    """You may edit, disable or change roles only of people ranked below you
    (directors may manage other directors)."""
    target = membership_rank(membership)
    return target < actor_rank or actor_rank >= TOP_SCHOOL_RANK


def approval_level(user, school):
    roles = set(user_roles(user, school).values_list("role", flat=True))
    return max([APPROVAL_LEVELS.get(r, 0) for r in roles] or [0])


def class_scope(user, school):
    """Class ids the user may work with, or None meaning every class.

    Built from class-teacher roles, subject allocations and, for heads of department,
    the classes where their department's subjects are taught."""
    from apps.curriculum.models import SubjectAllocation
    from apps.schoolsetup.models import SchoolClass, Stream

    assignments = list(user_roles(user, school))
    if any(a.role in SCHOOL_WIDE_ROLES for a in assignments):
        return None
    class_ids = set()
    for a in assignments:
        if a.scope_type == "class" and a.scope_id:
            class_ids.add(a.scope_id)
        elif a.scope_type == "stream" and a.scope_id:
            stream = Stream.objects.filter(pk=a.scope_id, school=school).first()
            if stream:
                class_ids.add(stream.school_class_id)
        elif a.scope_type == "section" and a.scope_id:
            class_ids |= set(
                SchoolClass.objects.filter(school=school, section_id=a.scope_id).values_list("id", flat=True)
            )
        elif a.role == "hod" and a.scope_type == "department" and a.scope_id:
            class_ids |= set(
                SubjectAllocation.objects.filter(
                    school=school, subject__department_id=a.scope_id
                ).values_list("school_class_id", flat=True)
            )
    class_ids |= set(
        SubjectAllocation.objects.filter(school=school, teacher__user=user).values_list(
            "school_class_id", flat=True
        )
    )
    return class_ids


def class_teacher_classes(school, assignments):
    """Ids of the classes the user is class teacher of (a whole class or one of its streams)."""
    from apps.schoolsetup.models import Stream

    ids = set()
    for a in assignments:
        if a.role != "class_teacher" or not a.scope_id:
            continue
        if a.scope_type == "class":
            ids.add(a.scope_id)
        elif a.scope_type == "stream":
            stream = Stream.objects.filter(pk=a.scope_id, school=school).first()
            if stream:
                ids.add(stream.school_class_id)
    return ids


def can_enter_marks(user, school, subject_id, class_id):
    """Subject teachers enter marks only for their allocated subject and class; class
    teachers for every subject of their own class (in primary the class teacher usually
    teaches them all); heads of department for subjects in their department; school-wide
    roles for all."""
    from apps.curriculum.models import Subject, SubjectAllocation

    assignments = list(user_roles(user, school))
    if any(a.role in SCHOOL_WIDE_ROLES for a in assignments):
        return True
    if class_id in class_teacher_classes(school, assignments):
        return True
    if SubjectAllocation.objects.filter(
        school=school, teacher__user=user, subject_id=subject_id, school_class_id=class_id
    ).exists():
        return True
    department_ids = {a.scope_id for a in assignments if a.role == "hod" and a.scope_type == "department"}
    if department_ids:
        return Subject.objects.filter(pk=subject_id, department_id__in=department_ids).exists()
    return False


def sync_class_teacher_role(school_class, old_teacher=None, new_teacher=None):
    """Class-teacher access to the class for exactly its class teacher and deputy.
    Teachers without a login simply have nothing to sync."""
    from apps.schoolsetup.class_teachers import sync_access

    sync_access(school_class)
