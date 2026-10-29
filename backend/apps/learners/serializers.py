from rest_framework import serializers

from apps.core.permissions import has_perm
from apps.core.serializers import LabelField, SchoolOwnedSerializer

from .models import (
    Enrolment,
    Guardian,
    Learner,
    LearnerDocument,
    LearnerExit,
    LearnerGuardian,
    StreamChange,
    SubjectEnrolment,
)

HEALTH_FIELDS = ("allergies", "medical_notes")


class GuardianSerializer(SchoolOwnedSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Guardian
        fields = [
            "id",
            "full_name",
            "phone",
            "alt_phone",
            "email",
            "occupation",
            "address",
            "nin",
            "children",
        ]

    def get_children(self, obj):
        return [
            {"id": link.learner_id, "name": link.learner.full_name, "relationship": link.relationship}
            for link in obj.learner_links.select_related("learner")
        ]


class LearnerGuardianSerializer(SchoolOwnedSerializer):
    guardian_detail = GuardianSerializer(source="guardian", read_only=True)

    class Meta:
        model = LearnerGuardian
        fields = [
            "id",
            "learner",
            "guardian",
            "guardian_detail",
            "relationship",
            "is_primary",
            "receives_email",
        ]


class EnrolmentSerializer(SchoolOwnedSerializer):
    class_name = LabelField("school_class.name")
    stream_name = LabelField("stream.name", default=None)
    term_label = LabelField("term")

    class Meta:
        model = Enrolment
        fields = [
            "id",
            "learner",
            "term",
            "term_label",
            "school_class",
            "class_name",
            "stream",
            "stream_name",
            "residence",
        ]

    def validate(self, attrs):
        stream = attrs.get("stream")
        school_class = attrs.get("school_class", getattr(self.instance, "school_class", None))
        if stream and school_class and stream.school_class_id != school_class.id:
            raise serializers.ValidationError({"stream": "The stream must belong to the chosen class."})
        return attrs


class LearnerSerializer(SchoolOwnedSerializer):
    full_name = serializers.CharField(read_only=True)
    current_class = serializers.SerializerMethodField()
    house_name = LabelField("house.name", default=None)
    medical_flag = serializers.SerializerMethodField()

    class Meta:
        model = Learner
        fields = [
            "id",
            "adm_no",
            "lin",
            "first_name",
            "last_name",
            "other_names",
            "full_name",
            "sex",
            "date_of_birth",
            "nationality",
            "religion",
            "photo",
            "address",
            "district",
            "previous_school",
            "house",
            "house_name",
            "combination",
            "residence",
            "status",
            "admitted_on",
            "year_of_entry",
            "allergies",
            "medical_notes",
            "has_medical_alert",
            "medical_flag",
            "special_needs",
            "notes",
            "current_class",
        ]
        extra_kwargs = {"adm_no": {"required": False, "allow_blank": True}, "status": {"read_only": True}}

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is None or not has_perm(request, "health.view"):
            for name in HEALTH_FIELDS:
                fields.pop(name, None)
        return fields

    def get_medical_flag(self, obj):
        # Everyone sees that there is an alert; only health roles see the details.
        return "See nurse" if obj.has_medical_alert else None

    def get_current_class(self, obj):
        enrolment = getattr(obj, "_current_enrolment", None) or obj.current_enrolment()
        if enrolment is None:
            return None
        return {
            "enrolment_id": enrolment.id,
            "term": enrolment.term_id,
            "class_id": enrolment.school_class_id,
            "class_name": enrolment.school_class.name,
            "stream_id": enrolment.stream_id,
            "stream_name": enrolment.stream.name if enrolment.stream else None,
        }

    def validate_adm_no(self, value):
        request = self.context["request"]
        if value:
            others = Learner.objects.filter(school=request.school, adm_no=value)
            if self.instance:
                others = others.exclude(pk=self.instance.pk)
            if others.exists():
                raise serializers.ValidationError("This admission number is already used.")
        return value


class LearnerCreateSerializer(LearnerSerializer):
    """Create a learner and place them in a class in one step."""

    school_class = serializers.IntegerField(write_only=True, required=False)
    term = serializers.IntegerField(write_only=True, required=False, help_text="Defaults to the current term")
    stream = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    guardian_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    guardian_phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    guardian_relationship = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta(LearnerSerializer.Meta):
        fields = LearnerSerializer.Meta.fields + [
            "school_class",
            "stream",
            "term",
            "guardian_name",
            "guardian_phone",
            "guardian_relationship",
        ]


class SubjectEnrolmentSerializer(SchoolOwnedSerializer):
    subject_name = LabelField("subject.name")

    class Meta:
        model = SubjectEnrolment
        fields = ["id", "learner", "subject", "subject_name", "academic_year"]


class LearnerDocumentSerializer(SchoolOwnedSerializer):
    class Meta:
        model = LearnerDocument
        fields = ["id", "learner", "title", "file", "created_at"]


class LearnerExitSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")

    class Meta:
        model = LearnerExit
        fields = ["id", "learner", "learner_name", "kind", "date", "destination_school", "reason"]


class StreamChangeSerializer(SchoolOwnedSerializer):
    class Meta:
        model = StreamChange
        fields = [
            "id",
            "learner",
            "term",
            "from_class",
            "from_stream",
            "to_class",
            "to_stream",
            "reason",
            "created_at",
        ]
        read_only_fields = ["from_class", "from_stream"]
