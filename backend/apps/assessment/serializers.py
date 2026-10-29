from rest_framework import serializers

from apps.core.serializers import LabelField, SchoolOwnedSerializer

from .models import (
    AOIScore,
    CommentBank,
    Exam,
    ExamSchedule,
    Mark,
    MarkSheet,
    NurseryRating,
    ReportCard,
    ResultSummary,
    UnebResult,
)


class ExamSerializer(SchoolOwnedSerializer):
    term_label = LabelField("term")

    class Meta:
        model = Exam
        fields = [
            "id",
            "term",
            "term_label",
            "name",
            "kind",
            "weight",
            "max_mark",
            "classes",
            "start_date",
            "end_date",
            "schedule_published_at",
        ]
        read_only_fields = ["schedule_published_at"]

    def validate_weight(self, value):
        if value <= 0 or value > 100:
            raise serializers.ValidationError("The weight must be between 0 and 100.")
        return value


class ExamScheduleSerializer(SchoolOwnedSerializer):
    subject_name = LabelField("subject.name")
    invigilator_name = LabelField("invigilator.full_name", default=None)
    room_name = LabelField("room.name", default=None)

    class Meta:
        model = ExamSchedule
        fields = [
            "id",
            "exam",
            "subject",
            "subject_name",
            "paper",
            "school_class",
            "date",
            "start_time",
            "end_time",
            "room",
            "room_name",
            "invigilator",
            "invigilator_name",
        ]

    def validate(self, attrs):
        get = lambda k: attrs.get(k, getattr(self.instance, k, None))  # noqa: E731
        overlapping = ExamSchedule.objects.filter(
            school=self.context["request"].school,
            date=get("date"),
            start_time__lt=get("end_time"),
            end_time__gt=get("start_time"),
        )
        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)
        errors = []
        if get("invigilator") and overlapping.filter(invigilator=get("invigilator")).exists():
            errors.append("The invigilator is already invigilating at this time.")
        if get("room") and overlapping.filter(room=get("room")).exists():
            errors.append("The room is already booked at this time.")
        if overlapping.filter(school_class=get("school_class")).exists():
            errors.append("This class already sits another paper at this time.")
        if errors:
            raise serializers.ValidationError({"clashes": errors})
        return attrs


class MarkSheetSerializer(SchoolOwnedSerializer):
    exam_name = LabelField("exam.name")
    subject_name = LabelField("subject.name")
    paper_label = serializers.SerializerMethodField()
    class_label = serializers.SerializerMethodField()
    status_label = LabelField("get_status_display")
    marks_entered = serializers.SerializerMethodField()

    class Meta:
        model = MarkSheet
        fields = [
            "id",
            "exam",
            "exam_name",
            "subject",
            "subject_name",
            "paper",
            "paper_label",
            "school_class",
            "stream",
            "class_label",
            "status",
            "status_label",
            "submitted_by",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "approved_by",
            "locked_at",
            "return_comment",
            "reopened_by",
            "reopen_reason",
            "marks_entered",
        ]
        read_only_fields = [
            "status",
            "submitted_by",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "approved_by",
            "locked_at",
            "return_comment",
            "reopened_by",
            "reopen_reason",
        ]

    def get_paper_label(self, obj):
        return f"Paper {obj.paper.number}" if obj.paper else ""

    def get_class_label(self, obj):
        return str(obj.stream or obj.school_class)

    def get_marks_entered(self, obj):
        return obj.marks.exclude(score__isnull=True, is_absent=False).count()


class MarkSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")

    class Meta:
        model = Mark
        fields = ["id", "mark_sheet", "learner", "learner_name", "score", "is_absent", "version"]


class AOIScoreSerializer(SchoolOwnedSerializer):
    class Meta:
        model = AOIScore
        fields = ["id", "learner", "competency", "term", "score", "remark"]

    def validate_score(self, value):
        if value < 0 or value > 3:
            raise serializers.ValidationError("AOI scores run from 0 to 3.")
        return value


class NurseryRatingSerializer(SchoolOwnedSerializer):
    class Meta:
        model = NurseryRating
        fields = ["id", "learner", "term", "learning_area", "rating", "remark"]


class ResultSummarySerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")
    adm_no = LabelField("learner.adm_no")

    class Meta:
        model = ResultSummary
        fields = [
            "id",
            "learner",
            "learner_name",
            "adm_no",
            "term",
            "school_class",
            "stream",
            "rule_set",
            "subjects",
            "total",
            "average",
            "aggregate",
            "division",
            "points",
            "position",
            "stream_position",
            "out_of",
            "is_complete",
            "computed_at",
        ]


class CommentBankSerializer(SchoolOwnedSerializer):
    subject_name = LabelField("subject.name", default=None)

    class Meta:
        model = CommentBank
        fields = ["id", "role", "subject", "subject_name", "min_average", "max_average", "text"]


class ReportCardSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")
    adm_no = LabelField("learner.adm_no")
    term_label = LabelField("term")
    summary = serializers.SerializerMethodField()

    class Meta:
        model = ReportCard
        fields = [
            "id",
            "learner",
            "learner_name",
            "adm_no",
            "term",
            "term_label",
            "serial",
            "status",
            "class_teacher_comment",
            "head_comment",
            "promotion_note",
            "published_at",
            "superseded_by",
            "summary",
        ]
        read_only_fields = [
            "learner",
            "term",
            "serial",
            "status",
            "published_at",
            "superseded_by",
            "promotion_note",
        ]

    def get_summary(self, obj):
        snap = obj.snapshot or {}
        return {
            k: snap.get(k)
            for k in ("average", "aggregate", "division", "points", "position", "out_of", "is_complete")
        }


class UnebResultSerializer(SchoolOwnedSerializer):
    class Meta:
        model = UnebResult
        fields = [
            "id",
            "year",
            "level",
            "index_number",
            "candidate_name",
            "learner",
            "sex",
            "subject_grades",
            "aggregate",
            "division",
            "points",
        ]
