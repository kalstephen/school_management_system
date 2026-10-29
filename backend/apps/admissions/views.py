import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet
from apps.learners.services import admit_learner, find_or_create_guardian
from apps.schoolsetup.models import current_term

from .models import Application, Enquiry, Visitor

PERMS = {"read": "admissions.view", "write": "admissions.manage"}


class ApplicationSerializer(SchoolOwnedSerializer):
    class_name = LabelField("class_applied.name")

    class Meta:
        model = Application
        fields = [
            "id",
            "first_name",
            "last_name",
            "other_names",
            "sex",
            "date_of_birth",
            "lin",
            "previous_school",
            "previous_results",
            "class_applied",
            "class_name",
            "term",
            "residence",
            "guardian_name",
            "guardian_phone",
            "guardian_email",
            "guardian_relationship",
            "channel",
            "status",
            "interview_date",
            "interview_score",
            "interview_notes",
            "placed_stream",
            "learner",
            "created_at",
        ]
        read_only_fields = ["learner"]


class EnquirySerializer(SchoolOwnedSerializer):
    class Meta:
        model = Enquiry
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "subject",
            "details",
            "follow_up_on",
            "is_closed",
            "created_at",
        ]


class VisitorSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Visitor
        fields = ["id", "name", "phone", "id_number", "purpose", "person_to_see", "time_in", "time_out"]


class ApplicationViewSet(SchoolViewSet):
    queryset = Application.objects.select_related("class_applied")
    serializer_class = ApplicationSerializer
    perms = PERMS
    module = "admissions"
    filterset_fields = ["status", "class_applied", "term", "channel"]
    search_fields = ["first_name", "last_name", "guardian_name", "guardian_phone", "lin"]

    @action(detail=True, methods=["post"])
    def admit(self, request, pk=None):
        """Turn an application into a learner: admission number, enrolment and guardian."""
        application = self.get_object()
        if application.learner_id:
            raise BusinessRuleError({"detail": "This applicant has already been admitted."})
        if application.status in (Application.Status.REJECTED, Application.Status.WITHDRAWN):
            raise BusinessRuleError({"detail": "Rejected or withdrawn applications cannot be admitted."})
        term = application.term or current_term(request.school)
        stream = application.placed_stream
        if request.data.get("stream"):
            stream = application.class_applied.streams.filter(pk=request.data["stream"]).first()
        with transaction.atomic():
            guardian = find_or_create_guardian(
                request.school,
                application.guardian_name,
                application.guardian_phone,
                application.guardian_email,
            )
            learner = admit_learner(
                request.school,
                {
                    "first_name": application.first_name,
                    "last_name": application.last_name,
                    "other_names": application.other_names,
                    "sex": application.sex,
                    "date_of_birth": application.date_of_birth,
                    "lin": application.lin,
                    "previous_school": application.previous_school,
                    "residence": application.residence,
                    "admitted_on": timezone.localdate(),
                    "year_of_entry": datetime.date.today().year,
                },
                term=term,
                school_class=application.class_applied,
                stream=stream,
                guardian=guardian,
                relationship=application.guardian_relationship,
            )
            application.learner = learner
            application.status = Application.Status.ADMITTED
            application.placed_stream = stream
            application.save()
        return Response({"learner_id": learner.id, "adm_no": learner.adm_no})


class EnquiryViewSet(SchoolViewSet):
    queryset = Enquiry.objects.all()
    serializer_class = EnquirySerializer
    perms = PERMS
    module = "admissions"
    filterset_fields = ["is_closed"]
    search_fields = ["name", "phone", "subject"]


class VisitorViewSet(SchoolViewSet):
    queryset = Visitor.objects.all()
    serializer_class = VisitorSerializer
    perms = PERMS
    module = "admissions"
    filterset_fields = {"time_in": ["date", "gte", "lte"]}
    search_fields = ["name", "phone", "purpose", "person_to_see"]

    @action(detail=True, methods=["post"], url_path="sign-out")
    def sign_out(self, request, pk=None):
        visitor = self.get_object()
        visitor.time_out = timezone.now()
        visitor.save()
        return Response(self.get_serializer(visitor).data)
