from rest_framework import serializers

from apps.core.serializers import LabelField, SchoolOwnedSerializer

from .models import Combination, Competency, Paper, SchemeOfWork, Subject, SubjectAllocation


class PaperSerializer(SchoolOwnedSerializer):
    label = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Paper
        fields = ["id", "subject", "number", "name", "label"]


class SubjectSerializer(SchoolOwnedSerializer):
    papers = PaperSerializer(many=True, read_only=True)
    status_label = LabelField("get_status_display")
    proposed_by_name = LabelField("proposed_by.display_name", default=None)
    decided_by_name = LabelField("decided_by.display_name", default=None)
    specialists = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        read_only_fields = ["status", "proposed_by", "decided_by", "decided_at"]
        fields = [
            "id",
            "name",
            "short_name",
            "uneb_code",
            "level",
            "category",
            "department",
            "classes",
            "in_aggregate",
            "order",
            "papers",
            "status",
            "status_label",
            "proposal_note",
            "proposed_by",
            "proposed_by_name",
            "decided_by",
            "decided_by_name",
            "decided_at",
            "specialists",
        ]

    def get_specialists(self, obj):
        return [s.full_name for s in obj.specialists.all()]


class CombinationSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Combination
        fields = ["id", "code", "name", "principals", "subsidiary"]


class CompetencySerializer(SchoolOwnedSerializer):
    subject_name = LabelField("subject.name")

    class Meta:
        model = Competency
        fields = ["id", "subject", "subject_name", "school_class", "topic", "description", "is_aoi"]


class SubjectAllocationSerializer(SchoolOwnedSerializer):
    teacher_name = LabelField("teacher.full_name")
    subject_name = LabelField("subject.name")
    class_name = LabelField("school_class.name")
    stream_name = LabelField("stream.name", default=None)

    class Meta:
        model = SubjectAllocation
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "subject",
            "subject_name",
            "school_class",
            "class_name",
            "stream",
            "stream_name",
            "periods_per_week",
        ]

    def validate(self, attrs):
        teacher = attrs.get("teacher", getattr(self.instance, "teacher", None))
        periods = attrs.get("periods_per_week", getattr(self.instance, "periods_per_week", 0))
        if teacher and teacher.max_periods_per_week:
            others = SubjectAllocation.objects.filter(teacher=teacher)
            if self.instance:
                others = others.exclude(pk=self.instance.pk)
            load = sum(others.values_list("periods_per_week", flat=True)) + periods
            if load > teacher.max_periods_per_week:
                raise serializers.ValidationError(
                    {
                        "teacher": f"This would give {teacher} {load} periods a week, above their limit of "
                        f"{teacher.max_periods_per_week}."
                    }
                )
        return attrs


class SchemeOfWorkSerializer(SchoolOwnedSerializer):
    subject_name = LabelField("subject.name")
    class_name = LabelField("school_class.name")

    class Meta:
        model = SchemeOfWork
        fields = [
            "id",
            "kind",
            "title",
            "subject",
            "subject_name",
            "school_class",
            "class_name",
            "term",
            "file",
            "notes",
            "created_by",
            "created_at",
        ]
