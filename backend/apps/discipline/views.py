from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet

from .models import Achievement, CounsellingReferral, DisciplineCase, Sanction

PERMS = {"read": "discipline.view", "write": "discipline.manage"}


class SanctionSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Sanction
        fields = ["id", "case", "kind", "start_date", "end_date", "notes"]


class DisciplineCaseSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")
    sanctions = SanctionSerializer(many=True, read_only=True)

    class Meta:
        model = DisciplineCase
        fields = [
            "id",
            "learner",
            "learner_name",
            "date",
            "category",
            "severity",
            "description",
            "reported_by",
            "action_taken",
            "status",
            "closed_on",
            "sanctions",
            "created_at",
        ]


class CounsellingReferralSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")

    class Meta:
        model = CounsellingReferral
        fields = ["id", "learner", "learner_name", "date", "reason", "referred_to", "status", "notes"]


class AchievementSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")

    class Meta:
        model = Achievement
        fields = ["id", "learner", "learner_name", "date", "title", "category", "description"]


class DisciplineCaseViewSet(SchoolViewSet):
    queryset = DisciplineCase.objects.select_related("learner").prefetch_related("sanctions")
    serializer_class = DisciplineCaseSerializer
    perms = PERMS
    module = "discipline"
    filterset_fields = {
        "learner": ["exact"],
        "status": ["exact"],
        "severity": ["exact"],
        "date": ["gte", "lte"],
    }
    search_fields = ["learner__first_name", "learner__last_name", "category", "description"]

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        from django.utils import timezone

        case = self.get_object()
        case.status, case.closed_on = DisciplineCase.Status.CLOSED, timezone.localdate()
        case.action_taken = request.data.get("action_taken", case.action_taken)
        case.save()
        return Response(self.get_serializer(case).data)


class SanctionViewSet(SchoolViewSet):
    queryset = Sanction.objects.all()
    serializer_class = SanctionSerializer
    perms = PERMS
    module = "discipline"
    filterset_fields = ["case"]


class CounsellingReferralViewSet(SchoolViewSet):
    queryset = CounsellingReferral.objects.select_related("learner")
    serializer_class = CounsellingReferralSerializer
    perms = PERMS
    module = "discipline"
    filterset_fields = ["learner", "status"]


class AchievementViewSet(SchoolViewSet):
    queryset = Achievement.objects.select_related("learner")
    serializer_class = AchievementSerializer
    perms = PERMS
    module = "discipline"
    filterset_fields = ["learner", "category"]
