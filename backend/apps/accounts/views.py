from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.context import reset_platform_session, set_platform_session
from apps.core.exceptions import BusinessRuleError
from apps.core.models import School
from apps.core.modules import ALL_MODULES, user_modules
from apps.core.viewsets import SchoolViewSet

from .models import Membership, PermissionGrant, RoleAssignment, User
from .roles import MEMBER_BASE, ROLE_DESCRIPTIONS, ROLE_LABELS, ROLE_PERMS, ROLE_RANK
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MembershipSerializer,
    PermissionGrantSerializer,
    RoleAssignmentSerializer,
)
from .services import (
    PLATFORM_PORTAL,
    PORTAL_SESSION_KEY,
    SCHOOL_PORTAL,
    SCHOOL_SESSION_KEY,
    active_memberships,
    approval_level,
    can_assign,
    can_manage,
    effective_perms,
    is_platform_account,
    rank_of,
    user_roles,
)


def me_payload(request):
    from apps.subscriptions.services import school_access

    user, school = request.user, request.school
    roles = user_roles(user, school) if school else []
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.display_name,
            "email": user.email,
            "phone": user.phone,
            # Platform rights only count in a session started at the platform console.
            "is_platform_admin": bool(getattr(request, "is_platform_session", False)),
        },
        "schools": [
            {"id": m.school.id, "name": m.school.name, "code": m.school.code}
            for m in active_memberships(user)
        ],
        "school": (
            {
                "id": school.id,
                "name": school.name,
                "short_name": school.short_name,
                "code": school.code,
                "location": school.location,
                "motto": school.motto,
                "logo": school.logo.url if school.logo else None,
                "other_income_enabled": school.other_income_enabled,
            }
            if school
            else None
        ),
        "roles": [
            {
                "role": r.role,
                "label": ROLE_LABELS.get(r.role, r.role),
                "scope_type": r.scope_type,
                "scope_id": r.scope_id,
            }
            for r in roles
        ],
        "perms": sorted(effective_perms(user, school)),
        "modules": user_modules(user, school) if school else [],
        "module_labels": ALL_MODULES,
        "access": school_access(school) if school else None,
        "approval_level": approval_level(user, school) if school else 0,
        "rank": rank_of(user, school),
        "is_superuser": bool(getattr(request, "is_platform_session", False) and user.is_superuser),
        "portal": request.session.get(PORTAL_SESSION_KEY, SCHOOL_PORTAL),
    }


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"ok": True})


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        candidate = User.objects.filter(username__iexact=username).first()
        if candidate and candidate.is_locked():
            return Response(
                {"detail": "Too many failed attempts. Try again in a few minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        user = authenticate(
            request,
            username=candidate.username if candidate else username,
            password=serializer.validated_data["password"],
        )
        if user is None:
            if candidate:
                candidate.failed_logins += 1
                if candidate.failed_logins >= settings.LOGIN_MAX_FAILURES:
                    candidate.locked_until = timezone.now() + timedelta(
                        minutes=settings.LOGIN_LOCKOUT_MINUTES
                    )
                    candidate.failed_logins = 0
                candidate.save(update_fields=["failed_logins", "locked_until"])
            return Response({"detail": "Wrong username or password."}, status=status.HTTP_400_BAD_REQUEST)
        user.failed_logins = 0
        user.locked_until = None
        user.save(update_fields=["failed_logins", "locked_until"])
        portal = serializer.validated_data.get("portal") or SCHOOL_PORTAL
        code = (serializer.validated_data.get("school_code") or "").strip()
        if portal == PLATFORM_PORTAL:
            if not is_platform_account(user):
                return Response(
                    {
                        "detail": "This sign-in is for the platform team. "
                        "Schools sign in on the school sign-in page."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            chosen = None
        else:
            if not code:
                return Response({"school_code": ["Enter your School ID, e.g. NewHope-003."]}, status=400)
            school = School.objects.filter(code__iexact=code).first()
            if school is not None and not school.is_active:
                return Response(
                    {
                        "detail": f"School {school.code} is not active yet. "
                        "Ask the platform team to activate it."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            chosen = active_memberships(user).filter(school__code__iexact=code).first()
            if chosen is None:
                return Response(
                    {"detail": f"This account does not belong to school {code}. Check the School ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        login(request, user)
        request.session[PORTAL_SESSION_KEY] = portal
        if chosen:
            request.session[SCHOOL_SESSION_KEY] = chosen.school_id
        request.school = chosen.school if chosen else None
        request.is_platform_session = portal == PLATFORM_PORTAL
        token = set_platform_session(request.is_platform_session)
        try:
            return Response(me_payload(request))
        finally:
            reset_platform_session(token)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"ok": True})


class MeView(APIView):
    def get(self, request):
        return Response(me_payload(request))


class SwitchSchoolView(APIView):
    def post(self, request):
        school_id = request.data.get("school_id")
        membership = active_memberships(request.user).filter(school_id=school_id).first()
        if not membership:
            return Response(
                {"detail": "You are not a member of that school."}, status=status.HTTP_403_FORBIDDEN
            )
        request.session[SCHOOL_SESSION_KEY] = membership.school_id
        request.school = membership.school
        return Response(me_payload(request))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            return Response({"current_password": ["The current password is wrong."]}, status=400)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        login(request, request.user)
        return Response({"ok": True})


def _guard_target(request, membership):
    """Nobody changes their own access, and nobody manages someone ranked at or above them."""
    if membership.user_id == request.user.id and not getattr(request, "is_platform_session", False):
        raise BusinessRuleError({"detail": "You cannot change your own access. Ask someone above you."})
    if not can_manage(rank_of(request.user, request.school), membership):
        raise BusinessRuleError(
            {"detail": "This person is at or above your level; only someone higher can change them."}
        )


class MembershipViewSet(SchoolViewSet):
    queryset = Membership.objects.select_related("user").prefetch_related("roles")
    serializer_class = MembershipSerializer
    perms = {"read": "users.manage", "write": "users.manage"}
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email", "user__phone"]
    filterset_fields = ["is_active"]
    ordering = ["user__first_name"]

    def perform_update(self, serializer):
        _guard_target(self.request, serializer.instance)
        serializer.save()


class RoleAssignmentViewSet(SchoolViewSet):
    queryset = RoleAssignment.objects.all()
    serializer_class = RoleAssignmentSerializer
    perms = {"read": "users.manage", "write": "users.manage"}
    filterset_fields = ["membership", "role"]

    def perform_create(self, serializer):
        membership = serializer.validated_data["membership"]
        role = serializer.validated_data["role"]
        _guard_target(self.request, membership)
        if not can_assign(rank_of(self.request.user, self.request.school), role):
            raise BusinessRuleError(
                {"role": f"You cannot give the {ROLE_LABELS[role]} role; it is at or above your level."}
            )
        serializer.save(school=self.request.school)

    def perform_destroy(self, instance):
        _guard_target(self.request, instance.membership)
        if not can_assign(rank_of(self.request.user, self.request.school), instance.role):
            raise BusinessRuleError({"detail": "You cannot remove a role at or above your level."})
        instance.delete()


class PermissionGrantViewSet(SchoolViewSet):
    queryset = PermissionGrant.objects.all()
    serializer_class = PermissionGrantSerializer
    perms = {"read": "users.manage", "write": "users.manage"}
    filterset_fields = ["membership", "permission"]

    def perform_create(self, serializer):
        _guard_target(self.request, serializer.validated_data["membership"])
        permission = serializer.validated_data["permission"]
        if permission not in effective_perms(self.request.user, self.request.school):
            raise BusinessRuleError({"permission": "You can only grant permissions you hold yourself."})
        if serializer.validated_data["expires_at"] <= timezone.now():
            raise BusinessRuleError({"expires_at": "The expiry must be in the future."})
        serializer.save(school=self.request.school)


class RoleCatalogView(APIView):
    """The access ladder: every school role from the highest rank down, with what it can
    do, and whether the current user may assign it."""

    def get(self, request):
        school = getattr(request, "school", None)
        actor_rank = rank_of(request.user, school) if school else 0
        rows = sorted(ROLE_LABELS, key=lambda r: -ROLE_RANK.get(r, 0))
        return Response(
            [
                {
                    "value": role,
                    "label": ROLE_LABELS[role],
                    "rank": ROLE_RANK.get(role, 0),
                    "description": ROLE_DESCRIPTIONS.get(role, ""),
                    "perms": sorted(ROLE_PERMS.get(role, set()) | MEMBER_BASE),
                    "assignable": can_assign(actor_rank, role),
                }
                for role in rows
            ]
        )
