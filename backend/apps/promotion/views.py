from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.services import class_scope
from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import has_perm
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet
from apps.schoolsetup.models import SchoolClass, Term

from . import services
from .models import PromotionBatch, PromotionDecision, PromotionRule


class PromotionRuleSerializer(SchoolOwnedSerializer):
    measure_label = LabelField("get_measure_display")

    class Meta:
        model = PromotionRule
        fields = [
            "id",
            "section",
            "school_class",
            "measure",
            "measure_label",
            "pass_mark",
            "probation_mark",
            "fail_below",
            "min_attendance",
        ]

    def validate(self, attrs):
        section = attrs.get("section", getattr(self.instance, "section", None))
        school_class = attrs.get("school_class", getattr(self.instance, "school_class", None))
        if not section and not school_class:
            raise serializers.ValidationError({"section": "Choose a section or a class."})
        return attrs


class PromotionDecisionSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")
    adm_no = LabelField("learner.adm_no")
    to_class_name = LabelField("to_class.name", default=None)
    to_stream_name = LabelField("to_stream.name", default=None)
    note = serializers.SerializerMethodField()
    overridden_by_name = LabelField("overridden_by.display_name", default=None)

    class Meta:
        model = PromotionDecision
        fields = [
            "id",
            "batch",
            "learner",
            "learner_name",
            "adm_no",
            "measure_value",
            "proposed",
            "final",
            "override_reason",
            "overridden_by",
            "overridden_by_name",
            "teacher_comment",
            "to_class",
            "to_class_name",
            "to_stream",
            "to_stream_name",
            "note",
        ]
        read_only_fields = fields

    def get_note(self, obj):
        return services.promotion_note(obj)


class PromotionBatchSerializer(SchoolOwnedSerializer):
    class_name = LabelField("school_class.name")
    term_label = LabelField("term")
    counts = serializers.SerializerMethodField()
    status_label = LabelField("get_status_display")
    class_teacher_name = LabelField("school_class.class_teacher.full_name", default=None)
    reviewed_by_name = LabelField("reviewed_by.display_name", default=None)
    recommended_by_name = LabelField("recommended_by.display_name", default=None)
    approved_by_name = LabelField("approved_by.display_name", default=None)
    measure_label = serializers.SerializerMethodField()

    class Meta:
        model = PromotionBatch
        fields = [
            "id",
            "term",
            "term_label",
            "school_class",
            "class_name",
            "class_teacher_name",
            "rule",
            "measure_label",
            "pass_mark",
            "status",
            "status_label",
            "stream_policy",
            "target_term",
            "reviewed_by_name",
            "reviewed_at",
            "teacher_note",
            "recommended_by_name",
            "recommended_at",
            "dos_note",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "director_note",
            "applied_at",
            "counts",
            "created_at",
        ]
        read_only_fields = [
            "rule",
            "pass_mark",
            "status",
            "target_term",
            "approved_by",
            "applied_at",
            "teacher_note",
            "dos_note",
            "director_note",
        ]

    def get_measure_label(self, obj):
        if obj.school_class.is_candidate_class:
            return "Candidate class: learners complete"
        return obj.rule.get_measure_display() if obj.rule else "Term average (%)"

    def get_counts(self, obj):
        counts = {}
        for final in obj.decisions.values_list("final", flat=True):
            counts[final] = counts.get(final, 0) + 1
        return counts


class PromotionRuleViewSet(SchoolViewSet):
    queryset = PromotionRule.objects.all()
    serializer_class = PromotionRuleSerializer
    perms = {"read": "promotion.view", "write": "promotion.manage"}
    module = "promotion"


class PromotionBatchViewSet(SchoolViewSet):
    queryset = PromotionBatch.objects.select_related("school_class", "term__academic_year")
    serializer_class = PromotionBatchSerializer
    # The chain: the class teacher prepares and reviews (promotion.review), the DOS changes
    # decisions and recommends (promotion.manage), the director approves (promotion.approve).
    perms = {"read": "promotion.view", "write": "promotion.review"}
    action_perms = {
        "comment": "promotion.review",
        "submit": "promotion.review",
        "override": "promotion.manage",
        "recommend": "promotion.manage",
        "send_back": "promotion.manage",
        "destroy": "promotion.manage",
        "approve": "promotion.approve",
        "apply": "promotion.approve",
        "undo": "promotion.approve",
    }
    module = "promotion"
    http_method_names = ["get", "post", "delete"]
    filterset_fields = ["term", "school_class", "status"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("school_class__class_teacher")
        scope = class_scope(self.request.user, self.request.school)
        return queryset if scope is None else queryset.filter(school_class_id__in=scope)

    def create(self, request, *args, **kwargs):
        term = Term.objects.filter(school=request.school, pk=request.data.get("term")).first()
        school_class = SchoolClass.objects.filter(
            school=request.school, pk=request.data.get("school_class")
        ).first()
        if term is None or school_class is None:
            raise BusinessRuleError({"detail": "Choose a term and a class."})
        scope = class_scope(request.user, request.school)
        if scope is not None and school_class.id not in scope:
            raise BusinessRuleError({"school_class": "You can prepare the list only for your own class."})
        batch = services.propose(
            term,
            school_class,
            request.data.get("stream_policy", "keep"),
            request.data.get("pass_mark"),
        )
        return Response(self.get_serializer(batch).data, status=201)

    def perform_destroy(self, instance):
        if (
            instance.status != PromotionBatch.Status.PROPOSED
            and instance.status != PromotionBatch.Status.UNDONE
        ):
            raise BusinessRuleError({"detail": "Undo the batch before deleting it."})
        instance.delete()

    @action(detail=True, methods=["get"])
    def decisions(self, request, pk=None):
        batch = self.get_object()
        rows = batch.decisions.select_related(
            "learner", "to_class", "to_stream", "batch__school_class"
        ).order_by("learner__first_name")
        return Response(PromotionDecisionSerializer(rows, many=True).data)

    @action(detail=True, methods=["post"])
    def override(self, request, pk=None):
        batch = self.get_object()
        decision = batch.decisions.filter(pk=request.data.get("decision")).first()
        if decision is None:
            raise BusinessRuleError({"decision": "Unknown learner decision."})
        if batch.status == PromotionBatch.Status.RECOMMENDED and not has_perm(request, "promotion.approve"):
            raise BusinessRuleError({"detail": "The list is with the director now; only they can change it."})
        decision = services.override(
            decision, request.data.get("final"), request.data.get("reason", ""), request.user
        )
        return Response(PromotionDecisionSerializer(decision).data)

    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        batch = self.get_object()
        decision = batch.decisions.filter(pk=request.data.get("decision")).first()
        if decision is None:
            raise BusinessRuleError({"decision": "Unknown learner decision."})
        return Response(
            PromotionDecisionSerializer(services.comment(decision, request.data.get("comment"))).data
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        batch = services.submit(self.get_object(), request.user, request.data.get("note", ""))
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=["post"])
    def recommend(self, request, pk=None):
        batch = services.recommend(self.get_object(), request.user, request.data.get("note", ""))
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=["post"], url_path="send-back")
    def send_back(self, request, pk=None):
        return Response(
            self.get_serializer(services.send_back(self.get_object(), request.data.get("note", ""))).data
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        batch = services.approve(self.get_object(), request.user, request.data.get("note", ""))
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        target = Term.objects.filter(school=request.school, pk=request.data.get("target_term")).first()
        if target is None:
            raise BusinessRuleError({"target_term": "Choose the first term of the new year."})
        return Response(self.get_serializer(services.apply(self.get_object(), target, request.user)).data)

    @action(detail=True, methods=["post"])
    def undo(self, request, pk=None):
        return Response(self.get_serializer(services.undo(self.get_object())).data)
