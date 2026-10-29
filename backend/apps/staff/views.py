import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import has_perm
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet

from . import serializers as s
from .models import DutyRoster, LeaveRequest, PlannerTask, Qualification, StaffAttendance, StaffProfile
from .services import create_staff_login

PERMS = {"read": "staff.view", "write": "staff.manage"}


class StaffProfileViewSet(SchoolViewSet):
    queryset = StaffProfile.objects.select_related("department").prefetch_related(
        "qualifications", "allocations", "classes_taught", "subjects"
    )
    serializer_class = s.StaffProfileSerializer
    perms = {"read": "dashboard.view", "write": "staff.manage"}
    action_perms = {"specialisations": "curriculum.manage"}
    module = "staff"
    # The owner console reads the staff list to pick class teachers while setting up classes.
    platform_setup = "read"
    filterset_fields = ["kind", "department", "status", "contract_type"]
    search_fields = ["first_name", "last_name", "staff_no", "phone", "tmis_number", "registration_number"]
    export_title = "Staff"

    @action(detail=True, methods=["post"])
    def specialisations(self, request, pk=None):
        """{"subjects": [ids]}: the subjects a teacher can teach. Also open to whoever manages
        the curriculum (DOS, heads of department), who may not edit the rest of the profile."""
        staff = self.get_object()
        serializer = self.get_serializer(
            staff, data={"subjects": request.data.get("subjects", [])}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self.get_serializer(staff).data)

    def _pop_posts(self, serializer):
        """Class-teacher posts sent with the form, checked against who may appoint."""
        posts = {
            post: serializer.validated_data.pop(key)
            for key, post in (("class_teacher_of", "class_teacher"), ("deputy_class_teacher_of", "deputy"))
            if key in serializer.validated_data
        }
        if posts and not has_perm(self.request, "classes.assign"):
            raise BusinessRuleError(
                {"class_teacher_of": "Only the DOS, head teacher, director or administrator can do this."}
            )
        return posts

    def _apply_posts(self, staff, posts):
        from apps.schoolsetup.class_teachers import set_posts_for_staff

        for post, value in posts.items():
            set_posts_for_staff(staff, post, value, self.request.user)

    def perform_create(self, serializer):
        login = {
            k: serializer.validated_data.pop(k, "")
            for k in ("login_username", "login_password", "login_role")
        }
        posts = self._pop_posts(serializer)
        # One step: if the sign-in or a post cannot be set (e.g. a weak password), nothing is saved.
        with transaction.atomic():
            staff = serializer.save(school=self.request.school)
            if login["login_username"]:
                staff.user = create_staff_login(self.request, staff, **login)
                staff.save()
            self._apply_posts(staff, {k: v for k, v in posts.items() if v})

    def perform_update(self, serializer):
        for key in ("login_username", "login_password", "login_role"):
            serializer.validated_data.pop(key, None)
        posts = self._pop_posts(serializer)
        with transaction.atomic():
            staff = serializer.save()
            self._apply_posts(staff, posts)


class QualificationViewSet(SchoolViewSet):
    queryset = Qualification.objects.all()
    serializer_class = s.QualificationSerializer
    perms = PERMS
    module = "staff"
    filterset_fields = ["staff"]


class LeaveRequestViewSet(SchoolViewSet):
    queryset = LeaveRequest.objects.select_related("staff")
    serializer_class = s.LeaveRequestSerializer
    perms = {"read": "dashboard.view", "write": "dashboard.view"}
    action_perms = {"approve": "hr.approve", "reject": "hr.approve"}
    module = "staff"
    filterset_fields = ["staff", "status", "kind"]

    def get_queryset(self):
        from apps.core.permissions import has_perm

        queryset = super().get_queryset()
        if has_perm(self.request, "staff.view"):
            return queryset
        return queryset.filter(staff__user=self.request.user)

    def perform_create(self, serializer):
        from apps.core.permissions import has_perm

        staff = serializer.validated_data["staff"]
        if staff.user_id != self.request.user.id and not has_perm(self.request, "staff.manage"):
            raise BusinessRuleError({"staff": "You can only request leave for yourself."})
        serializer.save(school=self.request.school)

    def _decide(self, request, status):
        leave = self.get_object()
        if leave.status != LeaveRequest.Status.PENDING:
            raise BusinessRuleError({"detail": "This request has already been decided."})
        leave.status = status
        leave.decided_by = request.user
        leave.decided_at = timezone.now()
        leave.decision_comment = request.data.get("comment", "")
        leave.save()
        if (
            status == LeaveRequest.Status.APPROVED
            and leave.start_date <= timezone.localdate() <= leave.end_date
        ):
            leave.staff.status = StaffProfile.Status.ON_LEAVE
            leave.staff.save()
        return Response(self.get_serializer(leave).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, LeaveRequest.Status.APPROVED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(request, LeaveRequest.Status.REJECTED)


class DutyRosterViewSet(SchoolViewSet):
    queryset = DutyRoster.objects.select_related("staff")
    serializer_class = s.DutyRosterSerializer
    perms = {"read": "dashboard.view", "write": "staff.manage"}
    module = "staff"
    filterset_fields = {"staff": ["exact"], "date": ["exact", "gte", "lte"]}


class StaffAttendanceViewSet(SchoolViewSet):
    queryset = StaffAttendance.objects.select_related("staff")
    serializer_class = s.StaffAttendanceSerializer
    perms = PERMS
    module = "staff"
    filterset_fields = {"staff": ["exact"], "date": ["exact", "gte", "lte"], "status": ["exact"]}


class PlannerTaskSerializer(SchoolOwnedSerializer):
    class_name = LabelField("school_class.name", default=None)
    owner = LabelField("user.display_name")

    class Meta:
        model = PlannerTask
        fields = [
            "id",
            "user",
            "owner",
            "week_start",
            "day",
            "title",
            "details",
            "school_class",
            "class_name",
            "priority",
            "done",
            "done_at",
            "created_at",
        ]
        read_only_fields = ["user", "done_at"]

    def validate_week_start(self, value):
        return value - datetime.timedelta(days=value.weekday())  # always the Monday


class PlannerTaskViewSet(SchoolViewSet):
    """Each teacher's weekly work planner. Everyone manages their own; people who can view
    staff (head teacher, DOS) can look at a teacher's planner with ?user=<id>."""

    queryset = PlannerTask.objects.select_related("school_class", "user")
    serializer_class = PlannerTaskSerializer
    perms = {"read": "dashboard.view", "write": "dashboard.view"}
    pagination_class = None
    filterset_fields = ["week_start", "done", "school_class"]

    def get_queryset(self):
        queryset = super().get_queryset()
        other = self.request.query_params.get("user")
        if other and self.action == "list" and has_perm(self.request, "staff.view"):
            return queryset.filter(user_id=other)
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, user=self.request.user)

    def perform_update(self, serializer):
        done = serializer.validated_data.get("done")
        extra = {}
        if done is True and not serializer.instance.done:
            extra["done_at"] = timezone.now()
        elif done is False:
            extra["done_at"] = None
        serializer.save(**extra)

    @action(detail=False, methods=["post"], url_path="carry-over")
    def carry_over(self, request):
        """Copy last week's unfinished items into this week."""
        week = datetime.date.fromisoformat(request.data.get("week_start") or str(timezone.localdate()))
        week -= datetime.timedelta(days=week.weekday())
        previous = week - datetime.timedelta(days=7)
        copied = 0
        for task in self.get_queryset().filter(week_start=previous, done=False):
            if not PlannerTask.objects.filter(user=request.user, week_start=week, title=task.title).exists():
                PlannerTask.objects.create(
                    school=request.school,
                    user=request.user,
                    week_start=week,
                    day=task.day,
                    title=task.title,
                    details=task.details,
                    school_class=task.school_class,
                    priority=task.priority,
                )
                copied += 1
        return Response({"copied": copied})
