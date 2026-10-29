"""Platform super-admin API (our team) and the school's own support-access switch."""

import datetime
import re

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Membership, RoleAssignment, User
from apps.accounts.roles import PLATFORM_ONLY, ROLE_LABELS
from apps.core.models import School
from apps.core.modules import (
    ADDON_MODULES,
    ALL_MODULES,
    MODULE_DESCRIPTIONS,
    REQUIRED_MODULES,
    module_enabled,
)
from apps.core.permissions import SchoolPermission

from .models import AccessRequest, ModuleChangeLog, Plan, SchoolModule, Subscription, SupportAccessGrant
from .services import apply_plan, school_access, set_module


class IsPlatformAdmin(BasePermission):
    message = "Platform administrators only."

    def has_permission(self, request, view):
        # Platform rights only in a session started at the platform console.
        return bool(getattr(request, "is_platform_session", False))


class IsSuperAdmin(BasePermission):
    message = "Super admin only."

    def has_permission(self, request, view):
        return bool(getattr(request, "is_platform_session", False) and request.user.is_superuser)


class SchoolAdministratorSerializer(serializers.Serializer):
    """A school's first top-level account, created by the platform team at onboarding."""

    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=["director", "school_admin", "head_teacher"], default="director")


class PlatformTeamSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "is_platform_admin",
            "is_superuser",
            "is_active",
            "last_login",
            "password",
        ]
        read_only_fields = ["is_superuser", "last_login"]

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        if not password:
            raise serializers.ValidationError({"password": "A password is required for a new account."})
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user


class PlatformTeamViewSet(viewsets.ModelViewSet):
    """Top level: the super admin manages the platform team (and can see every account)."""

    serializer_class = PlatformTeamSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return User.objects.filter(Q(is_platform_admin=True) | Q(is_superuser=True)).order_by("username")

    def perform_create(self, serializer):
        serializer.save(is_platform_admin=True)

    def perform_update(self, serializer):
        if (
            serializer.instance.pk == self.request.user.pk
            and serializer.validated_data.get("is_active") is False
        ):
            raise serializers.ValidationError({"is_active": "You cannot disable your own account."})
        serializer.save()


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["id", "plan", "status", "starts_on", "ends_on", "notes"]


SCHOOL_PROFILE_FIELDS = [
    "code",
    "name",
    "short_name",
    "motto",
    "registration_number",
    "emis_number",
    "uneb_centre_number",
    "ownership",
    "levels",
    "kind",
    "established",
    "region",
    "district",
    "county",
    "sub_county",
    "parish",
    "village",
    "address",
    "gps",
    "phone",
    "email",
    "website",
    "head_teacher_name",
    "head_teacher_phone",
    "head_teacher_email",
    "director_name",
    "director_phone",
    "director_email",
    "director_nin",
    "director_address",
    "report_template",
    "report_color",
    "report_show_photo",
    "is_active",
]


class PlatformSchoolSerializer(serializers.ModelSerializer):
    """The school's full profile as the platform team registers it, plus which modules it
    has. On create, `modules` (a list of keys) sets the school's modules in one go."""

    subscription = SubscriptionSerializer(read_only=True)
    addons = serializers.SerializerMethodField()
    module_map = serializers.SerializerMethodField()
    modules = serializers.ListField(
        child=serializers.ChoiceField(choices=list(ALL_MODULES)), write_only=True, required=False
    )
    usage = serializers.SerializerMethodField()
    location = serializers.CharField(read_only=True)

    class Meta:
        model = School
        fields = [
            "id",
            *SCHOOL_PROFILE_FIELDS,
            "location",
            "created_at",
            "subscription",
            "addons",
            "module_map",
            "modules",
            "usage",
        ]
        read_only_fields = ["created_at"]
        extra_kwargs = {"code": {"required": False, "allow_null": True, "allow_blank": True}}

    def validate_code(self, value):
        value = (value or "").strip() or None
        if value and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{2,39}", value):
            raise serializers.ValidationError("Use letters, numbers and dashes only, e.g. NewHope-003.")
        if (
            value
            and School.objects.filter(code__iexact=value)
            .exclude(pk=getattr(self.instance, "pk", None))
            .exists()
        ):
            raise serializers.ValidationError("This School ID is already used.")
        return value

    def get_addons(self, school):
        return {m: module_enabled(school, m) for m in ADDON_MODULES}

    def get_module_map(self, school):
        return {m: module_enabled(school, m) for m in ALL_MODULES}

    def create(self, validated_data):
        modules = validated_data.pop("modules", None)
        school = super().create(validated_data)
        if modules is not None:
            set_school_modules(school, modules, self.context["request"].user)
        return school

    def update(self, instance, validated_data):
        modules = validated_data.pop("modules", None)
        school = super().update(instance, validated_data)
        if modules is not None:
            set_school_modules(school, modules, self.context["request"].user)
        return school

    def get_usage(self, school):
        from apps.learners.models import Learner

        members = Membership.objects.filter(school=school).aggregate(
            users=Count("id", filter=Q(is_active=True)), last_login=Max("user__last_login")
        )
        return {
            "learners": Learner.objects.filter(school=school, status="active").count(),
            "active_users": members["users"],
            "last_login": members["last_login"],
        }


def set_school_modules(school, modules, user):
    """Tick exactly these modules for the school (required ones stay on). Only changes are logged."""
    wanted = set(modules) | REQUIRED_MODULES
    for key in ALL_MODULES:
        if key in REQUIRED_MODULES:
            continue
        if module_enabled(school, key) != (key in wanted):
            set_module(school, key, key in wanted, user=user)


class PlanViewSet(viewsets.ModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]


class PlatformSchoolViewSet(viewsets.ModelViewSet):
    """Register schools, set plans and subscription status, switch add-ons.
    Deliberately exposes no marks, health or finance records."""

    queryset = School.objects.select_related("subscription").order_by("name")
    serializer_class = PlatformSchoolSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    search_fields = ["name", "short_name", "email", "code", "district", "registration_number"]
    filterset_fields = ["district", "region", "ownership", "is_active"]
    # No DELETE: a school leaving the platform is deactivated (is_active=False) so its
    # records stay recoverable and exportable.
    http_method_names = ["get", "post", "patch", "head", "options"]

    @action(detail=True, methods=["post"])
    def subscription(self, request, pk=None):
        school = self.get_object()
        sub = Subscription.objects.filter(school=school).first()
        serializer = SubscriptionSerializer(sub, data=request.data, partial=sub is not None)
        serializer.is_valid(raise_exception=True)
        sub = serializer.save(school=school)
        if request.data.get("apply_plan_addons"):
            apply_plan(
                school, sub.plan, user=request.user, chosen_addons=request.data.get("chosen_addons", [])
            )
        return Response(PlatformSchoolSerializer(school).data)

    @action(detail=True, methods=["post"])
    def modules(self, request, pk=None):
        """Tick the school's modules in one go: {"modules": ["finance", "library", ...]}."""
        school = self.get_object()
        keys = request.data.get("modules")
        if not isinstance(keys, list) or any(k not in ALL_MODULES for k in keys):
            return Response({"modules": ["Send the list of module keys to switch on."]}, status=400)
        set_school_modules(school, keys, request.user)
        return Response(PlatformSchoolSerializer(school, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def module(self, request, pk=None):
        school = self.get_object()
        module = request.data.get("module")
        if module not in ALL_MODULES or module in REQUIRED_MODULES:
            return Response({"module": ["School setup and Learners are required and always on."]}, status=400)
        set_module(
            school,
            module,
            bool(request.data.get("enabled")),
            user=request.user,
            effective_from=request.data.get("effective_from") or None,
        )
        return Response(PlatformSchoolSerializer(school).data)

    @action(detail=True, methods=["get", "post"])
    def administrators(self, request, pk=None):
        """GET: the school's top-level accounts. POST: create (or link) its director, school
        administrator or head teacher — the people who then manage everyone else."""
        school = self.get_object()
        top_roles = ["director", "school_admin", "head_teacher"]
        if request.method == "POST":
            serializer = SchoolAdministratorSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = dict(serializer.validated_data)
            role, password = data.pop("role"), data.pop("password", "")
            with transaction.atomic():
                user = User.objects.filter(username__iexact=data["username"]).first()
                if user is None:
                    if not password:
                        return Response(
                            {"password": ["A password is required for a new account."]}, status=400
                        )
                    validate_password(password)
                    user = User(**data)
                    user.set_password(password)
                    user.save()
                membership, _ = Membership.objects.get_or_create(school=school, user=user)
                if not membership.is_active:
                    membership.is_active = True
                    membership.save()
                RoleAssignment.objects.get_or_create(
                    school=school, membership=membership, role=role, scope_type="school", scope_id=None
                )
        rows = RoleAssignment.objects.filter(school=school, role__in=top_roles).select_related(
            "membership__user"
        )
        return Response(
            [
                {
                    "username": r.membership.user.username,
                    "name": r.membership.user.display_name,
                    "role": r.role,
                    "active": r.membership.is_active,
                    "last_login": r.membership.user.last_login,
                }
                for r in rows
            ]
        )

    @action(detail=True, methods=["get"], url_path="report-preview")
    def report_preview(self, request, pk=None):
        """A sample report card in a chosen design (?template=modern&color=%23047857)."""
        from django.http import HttpResponse

        from apps.assessment.pdf import render_cards, sample_card

        school = self.get_object()
        pdf = render_cards(
            [sample_card(school)], request.query_params.get("template"), request.query_params.get("color")
        )
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="report-preview.pdf"'
        return response

    @action(detail=True, methods=["get"])
    def changes(self, request, pk=None):
        rows = ModuleChangeLog.objects.filter(school_id=pk).select_related("changed_by")[:200]
        return Response(
            [
                {
                    "module": r.module,
                    "enabled": r.enabled,
                    "effective_from": r.effective_from,
                    "changed_by": r.changed_by.username if r.changed_by else None,
                    "changed_at": r.changed_at,
                }
                for r in rows
            ]
        )


class PublicAccessRequestSerializer(serializers.ModelSerializer):
    # A field people never see; bots fill it in. Such requests are accepted and dropped.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = AccessRequest
        fields = [
            "kind",
            "school_name",
            "contact_name",
            "role",
            "phone",
            "email",
            "district",
            "levels",
            "learners",
            "message",
            "website",
        ]

    def validate_phone(self, value):
        digits = re.sub(r"\D", "", value)
        if len(digits) < 9:
            raise serializers.ValidationError("Give a phone number we can call, e.g. 0772 123456.")
        return value.strip()


class PublicAccessRequestView(APIView):
    """The website's "Request access" form. Open to anyone, limited to a few per hour per
    address. The platform team is emailed (when they have an email) and sees it in the
    owner console under Requests."""

    authentication_classes = []
    permission_classes = []
    throttle_scope = "access_request"

    def get_throttles(self):
        from rest_framework.throttling import ScopedRateThrottle

        return [ScopedRateThrottle()]

    def post(self, request):
        serializer = PublicAccessRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if data.pop("website", ""):
            return Response({"ok": True}, status=status.HTTP_201_CREATED)
        access_request = AccessRequest.objects.create(**data)
        notify_platform_team(access_request)
        return Response(
            {"ok": True, "reference": f"SPEX-{access_request.pk:05d}"}, status=status.HTTP_201_CREATED
        )


def notify_platform_team(access_request):
    """Email the platform team about a new request; the owner console shows it either way."""
    import logging

    from django.core.mail import EmailMessage

    recipients = list(
        User.objects.filter(Q(is_platform_admin=True) | Q(is_superuser=True), is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return
    r = access_request
    try:
        EmailMessage(
            f"SPEX School Manager: {r.get_kind_display().lower()} from {r.school_name}",
            "\n".join(
                [
                    f"{r.contact_name} ({r.role or 'role not given'}) of {r.school_name}"
                    f"{f', {r.district}' if r.district else ''}",
                    f"Phone: {r.phone}",
                    f"Email: {r.email or '-'}",
                    f"Levels: {r.levels or '-'} · About {r.learners or '?'} learners",
                    "",
                    r.message or "(no message)",
                    "",
                    "Follow it up in the owner console → Requests.",
                ]
            ),
            to=recipients,
        ).send()
    except Exception:  # noqa: BLE001 - a mail outage must not lose the request itself
        logging.getLogger(__name__).exception("Could not email the platform team about a request")


class AccessRequestSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    handled_by_name = serializers.CharField(source="handled_by.username", default=None, read_only=True)

    class Meta:
        model = AccessRequest
        fields = [
            "id",
            "kind",
            "kind_label",
            "school_name",
            "contact_name",
            "role",
            "phone",
            "email",
            "district",
            "levels",
            "learners",
            "message",
            "status",
            "status_label",
            "notes",
            "handled_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "kind",
            "school_name",
            "contact_name",
            "role",
            "phone",
            "email",
            "district",
            "levels",
            "learners",
            "message",
            "created_at",
            "updated_at",
        ]


class AccessRequestViewSet(viewsets.ModelViewSet):
    """Requests from the website, for the platform team to follow up."""

    queryset = AccessRequest.objects.select_related("handled_by")
    serializer_class = AccessRequestSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    http_method_names = ["get", "patch", "head", "options"]
    filterset_fields = ["status", "kind"]
    search_fields = ["school_name", "contact_name", "phone", "email", "district"]

    def perform_update(self, serializer):
        serializer.save(handled_by=self.request.user)


class SchoolAddonsView(APIView):
    """The school admin sees its add-ons and can hide an enabled one (not enable new ones)."""

    permission_classes = [IsAuthenticated, SchoolPermission]

    def get_required_perm(self, request):
        return "setup.view" if request.method == "GET" else PLATFORM_ONLY

    def get(self, request):
        rows = {r.module: r for r in SchoolModule.objects.filter(school=request.school)}
        return Response(
            [
                {
                    "module": key,
                    "label": label,
                    "in_plan": bool(rows.get(key) and rows[key].enabled),
                    "hidden": bool(rows.get(key) and rows[key].hidden_by_school),
                    "active": module_enabled(request.school, key),
                }
                for key, label in ADDON_MODULES.items()
            ]
        )

    def post(self, request):
        row = SchoolModule.objects.filter(school=request.school, module=request.data.get("module")).first()
        if row is None or not row.enabled:
            return Response(
                {"detail": "This add-on is not in your plan."}, status=status.HTTP_400_BAD_REQUEST
            )
        row.hidden_by_school = bool(request.data.get("hidden"))
        row.changed_by = request.user
        row.save()
        return self.get(request)


class SupportAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportAccessGrant
        fields = ["id", "reason", "expires_at", "granted_by", "created_at"]
        read_only_fields = ["granted_by", "created_at"]


class SupportAccessViewSet(viewsets.ModelViewSet):
    """The school grants (and revokes) time-limited read access to the platform team."""

    serializer_class = SupportAccessSerializer
    permission_classes = [IsAuthenticated, SchoolPermission]
    http_method_names = ["get", "post", "delete"]

    def get_required_perm(self, request):
        return "users.manage"

    def get_queryset(self):
        return SupportAccessGrant.objects.filter(school=self.request.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, granted_by=self.request.user)


class AccessStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = getattr(request, "school", None)
        return Response({"access": school_access(school) if school else None})


class ModuleCatalogView(APIView):
    """Every module in the system, for the tick lists."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            [
                {
                    "key": key,
                    "label": label,
                    "description": MODULE_DESCRIPTIONS.get(key, ""),
                    "group": "add-on" if key in ADDON_MODULES else "core",
                    "required": key in REQUIRED_MODULES,
                }
                for key, label in ALL_MODULES.items()
            ]
        )


def module_enabled_list(school):
    return [m for m in ALL_MODULES if module_enabled(school, m)]


class PlatformUserSerializer(serializers.ModelSerializer):
    """A person's account in one school, created by the platform team: pick the school
    (its location comes with it), give a role, and tick which of the school's modules
    they inherit (none ticked = all of them)."""

    school = serializers.PrimaryKeyRelatedField(queryset=School.objects.all())
    school_name = serializers.CharField(source="school.name", read_only=True)
    school_code = serializers.CharField(source="school.code", read_only=True)
    school_location = serializers.CharField(source="school.location", read_only=True)
    username = serializers.CharField(source="user.username")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    email = serializers.EmailField(source="user.email", required=False, allow_blank=True)
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=list(ROLE_LABELS.items()), write_only=True, required=False)
    roles = serializers.SerializerMethodField()
    modules = serializers.ListField(child=serializers.ChoiceField(choices=list(ALL_MODULES)), required=False)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id",
            "school",
            "school_name",
            "school_code",
            "school_location",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "password",
            "title",
            "role",
            "roles",
            "modules",
            "is_active",
            "last_login",
        ]

    def get_roles(self, obj):
        return [ROLE_LABELS.get(r, r) for r in obj.roles.values_list("role", flat=True)]

    def validate(self, attrs):
        school = attrs.get("school", getattr(self.instance, "school", None))
        modules = attrs.get("modules")
        if school and modules:
            outside = sorted(set(modules) - set(module_enabled_list(school)))
            if outside:
                names = ", ".join(ALL_MODULES[m] for m in outside)
                raise serializers.ValidationError({"modules": [f"{school.name} does not have: {names}."]})
        if attrs.get("password"):
            validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        password = validated_data.pop("password", "")
        role = validated_data.pop("role", None)
        school = validated_data["school"]
        with transaction.atomic():
            user = User.objects.filter(username__iexact=user_data["username"]).first()
            if user is None:
                if not password:
                    raise serializers.ValidationError(
                        {"password": ["A password is required for a new account."]}
                    )
                user = User(**user_data)
                user.set_password(password)
                user.save()
            if Membership.objects.filter(school=school, user=user).exists():
                raise serializers.ValidationError(
                    {"username": [f"{user.username} already belongs to {school.name}."]}
                )
            membership = Membership.objects.create(user=user, **validated_data)
            if role:
                RoleAssignment.objects.create(school=school, membership=membership, role=role)
        return membership

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        password = validated_data.pop("password", "")
        role = validated_data.pop("role", None)
        validated_data.pop("school", None)  # an account stays in its school
        user_data.pop("username", None)
        for key, value in user_data.items():
            setattr(instance.user, key, value)
        if password:
            instance.user.set_password(password)
        instance.user.save()
        if role:
            RoleAssignment.objects.get_or_create(
                school=instance.school, membership=instance, role=role, scope_type="school", scope_id=None
            )
        return super().update(instance, validated_data)


class PlatformUserViewSet(viewsets.ModelViewSet):
    """Every school account on the platform, filterable by school."""

    queryset = (
        Membership.objects.select_related("user", "school")
        .prefetch_related("roles")
        .order_by("school__name", "user__first_name")
    )
    serializer_class = PlatformUserSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ["school", "is_active"]
    search_fields = [
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__phone",
        "school__name",
        "school__code",
    ]


class PlatformOverviewView(APIView):
    """The platform dashboard: every school, its status and exactly which modules it has."""

    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        from apps.learners.models import Learner

        today = timezone.localdate()
        schools = list(School.objects.select_related("subscription__plan").order_by("name"))
        learners = dict(
            Learner.objects.filter(status="active").values_list("school_id").annotate(n=Count("id"))
        )
        users = dict(
            Membership.objects.filter(is_active=True).values_list("school_id").annotate(n=Count("id"))
        )
        by_status = {"active": 0, "trial": 0, "suspended": 0, "expired": 0, "none": 0}
        adoption = dict.fromkeys(ALL_MODULES, 0)
        rows = []
        for school in schools:
            sub = getattr(school, "subscription", None)
            if sub is None:
                status_ = "none"
            elif sub.status != "suspended" and sub.ends_on < today:
                status_ = "expired"
            else:
                status_ = sub.status
            by_status[status_] = by_status.get(status_, 0) + 1
            modules = {key: module_enabled(school, key) for key in ALL_MODULES}
            for key, on in modules.items():
                adoption[key] += int(on)
            rows.append(
                {
                    "id": school.id,
                    "code": school.code,
                    "name": school.name,
                    "district": school.district,
                    "region": school.region,
                    "location": school.location,
                    "is_active": school.is_active,
                    "status": status_,
                    "plan": sub.plan.name if sub else None,
                    "ends_on": sub.ends_on if sub else None,
                    "learners": learners.get(school.id, 0),
                    "users": users.get(school.id, 0),
                    "modules": modules,
                    "head_teacher": school.head_teacher_name,
                    "director": school.director_name,
                }
            )
        soon = today + datetime.timedelta(days=30)
        return Response(
            {
                "totals": {
                    "schools": len(schools),
                    "active_schools": sum(1 for s in schools if s.is_active),
                    "learners": sum(learners.values()),
                    "users": sum(users.values()),
                    "by_status": by_status,
                },
                "module_adoption": [
                    {
                        "key": key,
                        "label": label,
                        "schools": adoption[key],
                        "required": key in REQUIRED_MODULES,
                    }
                    for key, label in ALL_MODULES.items()
                ],
                "schools": rows,
                "new_requests": AccessRequest.objects.filter(status=AccessRequest.Status.NEW).count(),
                "expiring_soon": [r for r in rows if r["ends_on"] and today <= r["ends_on"] <= soon],
                "recent_changes": [
                    {
                        "school": c.school.name,
                        "module": ALL_MODULES.get(c.module, c.module),
                        "enabled": c.enabled,
                        "by": c.changed_by.username if c.changed_by else None,
                        "at": c.changed_at,
                    }
                    for c in ModuleChangeLog.objects.select_related("school", "changed_by")[:15]
                ],
            }
        )
