from django.db.models import Sum
from rest_framework import serializers

from apps.core.serializers import LabelField, SchoolOwnedSerializer

from .models import DutyRoster, LeaveRequest, Qualification, StaffAttendance, StaffProfile


class QualificationSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Qualification
        fields = ["id", "staff", "title", "institution", "year", "document"]


class StaffProfileSerializer(SchoolOwnedSerializer):
    full_name = serializers.CharField(read_only=True)
    department_name = LabelField("department.name", default=None)
    teaching_load = serializers.SerializerMethodField()
    qualifications = QualificationSerializer(many=True, read_only=True)
    username = serializers.CharField(source="user.username", read_only=True, default=None)
    classes_taught = serializers.SerializerMethodField()
    # Optional: create the person's sign-in at the same time.
    login_username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    login_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )
    login_role = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Class-teacher posts, e.g. "class:12" or "stream:5" (empty removes the person from that post).
    class_posts = serializers.SerializerMethodField()
    subject_names = serializers.SerializerMethodField()
    class_teacher_of = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    deputy_class_teacher_of = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )

    class Meta:
        model = StaffProfile
        fields = [
            "id",
            "user",
            "username",
            "classes_taught",
            "class_posts",
            "class_teacher_of",
            "deputy_class_teacher_of",
            "login_username",
            "login_password",
            "login_role",
            "staff_no",
            "first_name",
            "last_name",
            "other_names",
            "full_name",
            "sex",
            "date_of_birth",
            "nin",
            "phone",
            "email",
            "photo",
            "kind",
            "designation",
            "department",
            "department_name",
            "tmis_number",
            "registration_number",
            "highest_qualification",
            "subjects",
            "subject_names",
            "specialisation",
            "contract_type",
            "contract_start",
            "contract_end",
            "max_periods_per_week",
            "status",
            "teaching_load",
            "qualifications",
        ]

    def get_classes_taught(self, obj):
        return [c["label"] for c in self.get_class_posts(obj) if c["post"] == "class_teacher"]

    def get_subject_names(self, obj):
        return [f"{s.name} ({s.get_level_display()})" for s in obj.subjects.all()]

    def validate_subjects(self, value):
        pending = [s.name for s in value if s.status != "approved"]
        if pending:
            raise serializers.ValidationError(f"Not approved yet: {', '.join(pending)}.")
        return value

    def get_class_posts(self, obj):
        from apps.schoolsetup.class_teachers import posts_of

        return posts_of(obj)

    def get_teaching_load(self, obj):
        return obj.allocations.aggregate(total=Sum("periods_per_week"))["total"] or 0


class LeaveRequestSerializer(SchoolOwnedSerializer):
    staff_name = LabelField("staff.full_name")
    days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "staff",
            "staff_name",
            "kind",
            "start_date",
            "end_date",
            "days",
            "reason",
            "status",
            "decided_by",
            "decided_at",
            "decision_comment",
            "created_at",
        ]
        read_only_fields = ["status", "decided_by", "decided_at"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "Leave must end on or after the start date."})
        return attrs


class DutyRosterSerializer(SchoolOwnedSerializer):
    staff_name = LabelField("staff.full_name")

    class Meta:
        model = DutyRoster
        fields = ["id", "staff", "staff_name", "date", "duty", "notes"]


class StaffAttendanceSerializer(SchoolOwnedSerializer):
    staff_name = LabelField("staff.full_name")

    class Meta:
        model = StaffAttendance
        fields = ["id", "staff", "staff_name", "date", "status", "time_in", "time_out"]
