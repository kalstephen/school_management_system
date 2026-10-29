from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.roles import PLATFORM_ONLY
from apps.accounts.services import user_roles
from apps.core.exceptions import BusinessRuleError
from apps.core.viewsets import SchoolViewSet

from . import serializers as s
from .models import Combination, Competency, Paper, SchemeOfWork, Subject, SubjectAllocation

PERMS = {"read": "dashboard.view", "write": "curriculum.manage"}
# The subject list is part of the school's setup, done in the owner console.
SETUP_PERMS = {"read": "dashboard.view", "write": PLATFORM_ONLY}


class SubjectViewSet(SchoolViewSet):
    """The owner console keeps the standard list. In the school, the director, DOS, head
    teacher or head of department propose a subject (it waits as pending) and the head
    teacher, director or DOS approves it; nobody but the director approves their own."""

    queryset = Subject.objects.prefetch_related("papers", "classes", "specialists").select_related(
        "proposed_by", "decided_by"
    )
    serializer_class = s.SubjectSerializer
    perms = SETUP_PERMS
    action_perms = {"create": "curriculum.propose", "decide": "curriculum.approve"}
    platform_setup = True
    module = "curriculum"
    filterset_fields = ["level", "category", "department", "classes", "status"]
    search_fields = ["name", "short_name", "uneb_code"]

    def get_queryset(self):
        queryset = super().get_queryset()
        # Lists and pickers show approved subjects unless proposals are asked for.
        if "status" not in self.request.query_params and self.action == "list":
            queryset = queryset.filter(status=Subject.Status.APPROVED)
        return queryset

    def perform_create(self, serializer):
        if getattr(self.request, "platform_setup", False):
            serializer.save(school=self.request.school, status=Subject.Status.APPROVED)
            return
        name = serializer.validated_data["name"].strip()
        level = serializer.validated_data["level"]
        if (
            Subject.objects.filter(school=self.request.school, level=level, name__iexact=name)
            .exclude(status=Subject.Status.REJECTED)
            .exists()
        ):
            raise BusinessRuleError({"name": f"{name} is already on the list (or waiting for approval)."})
        serializer.save(
            school=self.request.school, status=Subject.Status.PENDING, proposed_by=self.request.user
        )

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        """{"decision": "approve" | "reject"}: the head teacher, director or DOS decides."""
        subject = self.get_object()
        if subject.status != Subject.Status.PENDING:
            raise BusinessRuleError({"detail": "Only subjects waiting for approval can be decided."})
        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            raise BusinessRuleError({"decision": "Approve or reject."})
        is_director = user_roles(request.user, request.school).filter(role="director").exists()
        if subject.proposed_by_id == request.user.pk and not is_director:
            raise BusinessRuleError({"detail": "Someone else must approve a subject you proposed."})
        subject.status = Subject.Status.APPROVED if decision == "approve" else Subject.Status.REJECTED
        subject.decided_by, subject.decided_at = request.user, timezone.now()
        subject.save()
        return Response(self.get_serializer(subject).data)


class PaperViewSet(SchoolViewSet):
    queryset = Paper.objects.select_related("subject")
    serializer_class = s.PaperSerializer
    perms = SETUP_PERMS
    platform_setup = True
    module = "curriculum"
    filterset_fields = ["subject"]


class CombinationViewSet(SchoolViewSet):
    queryset = Combination.objects.prefetch_related("principals")
    serializer_class = s.CombinationSerializer
    perms = SETUP_PERMS
    platform_setup = True
    module = "curriculum"


class CompetencyViewSet(SchoolViewSet):
    queryset = Competency.objects.all()
    serializer_class = s.CompetencySerializer
    perms = PERMS
    module = "curriculum"
    filterset_fields = ["subject", "school_class", "is_aoi"]


class SubjectAllocationViewSet(SchoolViewSet):
    queryset = SubjectAllocation.objects.select_related("teacher", "subject", "school_class", "stream")
    serializer_class = s.SubjectAllocationSerializer
    perms = PERMS
    module = "curriculum"
    filterset_fields = ["teacher", "subject", "school_class", "stream"]

    @action(detail=False, methods=["post"], url_path="from-specialisations")
    def from_specialisations(self, request):
        """Give every subject of every class (or the chosen classes) a teacher who specialises
        in it, where none is allocated yet. Existing allocations are kept."""
        from .services import allocate_from_specialisations

        return Response(allocate_from_specialisations(request.school, request.data.get("classes") or None))


class SchemeOfWorkViewSet(SchoolViewSet):
    queryset = SchemeOfWork.objects.select_related("subject", "school_class")
    serializer_class = s.SchemeOfWorkSerializer
    perms = {"read": "curriculum.view", "write": "marks.enter"}
    module = "curriculum"
    filterset_fields = ["subject", "school_class", "term", "kind"]
