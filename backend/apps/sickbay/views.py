import datetime

from django.db.models import Count
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.audit import log_access
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet

from .models import Immunisation, SickbayVisit

PERMS = {"read": "health.view", "write": "health.manage"}


class SickbayVisitSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")

    class Meta:
        model = SickbayVisit
        fields = [
            "id",
            "learner",
            "learner_name",
            "visited_at",
            "complaint",
            "temperature",
            "diagnosis",
            "treatment",
            "outcome",
            "referred_to",
            "guardian_informed",
        ]


class ImmunisationSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")

    class Meta:
        model = Immunisation
        fields = ["id", "learner", "learner_name", "vaccine", "dose", "date", "notes"]


class HealthLoggedViewSet(SchoolViewSet):
    """Health records: every read is written to the access log."""

    resource = ""

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if request.query_params.get("learner"):
            log_access(request.school, self.resource, request.query_params["learner"])
        return response

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        log_access(request.school, self.resource, response.data.get("learner"))
        return response


class SickbayVisitViewSet(HealthLoggedViewSet):
    queryset = SickbayVisit.objects.select_related("learner")
    serializer_class = SickbayVisitSerializer
    perms = PERMS
    module = "sickbay"
    resource = "sickbay.visit"
    filterset_fields = {"learner": ["exact"], "outcome": ["exact"], "visited_at": ["date", "gte", "lte"]}
    search_fields = ["learner__first_name", "learner__last_name", "complaint", "diagnosis"]

    @action(detail=False, methods=["get"])
    def frequent(self, request):
        """Learners with three or more visits in the last 30 days (early-warning flag)."""
        since = timezone.now() - datetime.timedelta(days=30)
        rows = (
            self.get_queryset()
            .filter(visited_at__gte=since)
            .values("learner_id", "learner__first_name", "learner__last_name")
            .annotate(visits=Count("id"))
            .filter(visits__gte=3)
            .order_by("-visits")
        )
        return Response(
            [
                {
                    "learner": r["learner_id"],
                    "name": f"{r['learner__first_name']} {r['learner__last_name']}",
                    "visits": r["visits"],
                }
                for r in rows
            ]
        )


class ImmunisationViewSet(HealthLoggedViewSet):
    queryset = Immunisation.objects.select_related("learner")
    serializer_class = ImmunisationSerializer
    perms = PERMS
    module = "sickbay"
    resource = "sickbay.immunisation"
    filterset_fields = ["learner", "vaccine"]
