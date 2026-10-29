from rest_framework import serializers

from apps.core.models import School
from apps.core.serializers import LabelField, SchoolOwnedSerializer

from .models import (
    AcademicYear,
    CalendarEvent,
    Club,
    Department,
    GradeBand,
    GradingScale,
    House,
    SchoolClass,
    Section,
    Stream,
    Term,
)


class SchoolProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        exclude = ["next_adm_seq", "is_active"]
        # The report card design is agreed with the platform owners and set in the owner console.
        read_only_fields = ["created_at", "code", "report_template"]

    def validate_adm_no_format(self, value):
        if "{seq" not in value:
            raise serializers.ValidationError(
                "Include {seq:04d} where the running number goes, e.g. NH/{year}/{seq:04d}."
            )
        try:
            value.format(year=2026, seq=1)
        except (KeyError, IndexError, ValueError):
            raise serializers.ValidationError("Use only {year} and {seq:04d} in the pattern.")
        return value


class AcademicYearSerializer(SchoolOwnedSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "name", "start_date", "end_date", "is_current"]


class TermSerializer(SchoolOwnedSerializer):
    label = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Term
        fields = [
            "id",
            "academic_year",
            "number",
            "label",
            "start_date",
            "end_date",
            "status",
            "next_term_begins",
        ]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "The term must end after it starts."})
        return attrs


class SectionSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Section
        fields = ["id", "name", "level", "grading_rule_set", "grading_scale", "show_positions", "order"]


class StreamSerializer(SchoolOwnedSerializer):
    label = serializers.CharField(source="__str__", read_only=True)
    class_teacher_name = LabelField("class_teacher.full_name", default=None)
    deputy_class_teacher_name = LabelField("deputy_class_teacher.full_name", default=None)

    class Meta:
        model = Stream
        fields = [
            "id",
            "school_class",
            "name",
            "label",
            "capacity",
            "class_teacher",
            "class_teacher_name",
            "deputy_class_teacher",
            "deputy_class_teacher_name",
        ]
        read_only_fields = ["class_teacher", "deputy_class_teacher"]


class SchoolClassSerializer(SchoolOwnedSerializer):
    """A class such as P5. On save you can also give its streams by name and its class
    teacher; the class teacher is given class-teacher access to this class automatically."""

    section_name = LabelField("section.name")
    rule_set = LabelField("section.grading_rule_set")
    level = LabelField("section.level")
    streams = StreamSerializer(many=True, read_only=True)
    stream_names = serializers.ListField(
        child=serializers.CharField(max_length=30, allow_blank=True),
        write_only=True,
        required=False,
        help_text="Streams to add, e.g. ['East', 'West']. Existing streams are kept.",
    )
    class_teacher_name = LabelField("class_teacher.full_name", default=None)
    deputy_class_teacher_name = LabelField("deputy_class_teacher.full_name", default=None)
    next_class_name = LabelField("next_class.name", default=None)
    learners = serializers.SerializerMethodField()

    class Meta:
        model = SchoolClass
        fields = [
            "id",
            "section",
            "section_name",
            "rule_set",
            "level",
            "name",
            "order",
            "is_candidate_class",
            "next_class",
            "next_class_name",
            "class_teacher",
            "class_teacher_name",
            "deputy_class_teacher",
            "deputy_class_teacher_name",
            "streams",
            "stream_names",
            "learners",
        ]

    def get_learners(self, obj):
        from .models import current_term

        term = current_term(obj.school)
        return obj.enrolments.filter(term=term).count() if term else 0

    def validate(self, attrs):
        candidate = attrs.get("is_candidate_class", getattr(self.instance, "is_candidate_class", False))
        next_class = attrs.get("next_class", getattr(self.instance, "next_class", None))
        if candidate and next_class:
            raise serializers.ValidationError(
                {"next_class": "A candidate class (P7, S4, S6) does not promote; its learners complete."}
            )
        if self.instance and next_class and next_class.pk == self.instance.pk:
            raise serializers.ValidationError({"next_class": "A class cannot promote into itself."})
        names = [n.strip() for n in attrs.get("stream_names", []) if n.strip()]
        if len({n.lower() for n in names}) != len(names):
            raise serializers.ValidationError({"stream_names": "Each stream name must be different."})
        attrs["stream_names"] = names
        return attrs

    def create(self, validated_data):
        names = validated_data.pop("stream_names", [])
        school_class = super().create(validated_data)
        self._after_save(school_class, names, previous_teacher=None)
        return school_class

    def update(self, instance, validated_data):
        names = validated_data.pop("stream_names", [])
        previous = instance.class_teacher
        school_class = super().update(instance, validated_data)
        self._after_save(school_class, names, previous_teacher=previous)
        return school_class

    def _after_save(self, school_class, names, previous_teacher):
        from apps.accounts.services import sync_class_teacher_role

        for name in names:
            Stream.objects.get_or_create(
                school=school_class.school,
                school_class=school_class,
                name__iexact=name,
                defaults={"name": name},
            )
        if (
            school_class.deputy_class_teacher_id
            and school_class.deputy_class_teacher_id == school_class.class_teacher_id
        ):
            school_class.deputy_class_teacher = None
            school_class.save(update_fields=["deputy_class_teacher"])
        sync_class_teacher_role(school_class, previous_teacher, school_class.class_teacher)


class HouseSerializer(SchoolOwnedSerializer):
    class Meta:
        model = House
        fields = ["id", "name", "colour"]


class DepartmentSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Department
        fields = ["id", "name"]


class ClubSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Club
        fields = ["id", "name", "patron"]


class GradeBandSerializer(SchoolOwnedSerializer):
    class Meta:
        model = GradeBand
        fields = ["id", "scale", "label", "min_score", "max_score", "points", "descriptor"]


class GradingScaleSerializer(SchoolOwnedSerializer):
    bands = GradeBandSerializer(many=True, read_only=True)

    class Meta:
        model = GradingScale
        fields = ["id", "name", "bands"]


class CalendarEventSerializer(SchoolOwnedSerializer):
    class Meta:
        model = CalendarEvent
        fields = ["id", "title", "kind", "start_date", "end_date", "description"]
