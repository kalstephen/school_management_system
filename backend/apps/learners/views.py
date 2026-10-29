import datetime

from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.services import class_scope
from apps.core.audit import log_access
from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import has_perm
from apps.core.viewsets import SchoolViewSet
from apps.schoolsetup.models import SchoolClass, Stream, current_term

from . import serializers as s
from .excel import COLUMNS, build_template, create_learner, import_learners, validate_row
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
from .services import IMPORT_COLUMNS, admit_learner, find_or_create_guardian, import_learners_csv

PERMS = {"read": "learners.view", "write": "learners.manage"}


def enrolment_target(request, data):
    """The term, class and stream new learners join, checked against the user's classes.

    The term can be given directly, or as an academic year: then the year's open term is
    used (else the one running today, else its first term). A class teacher may only
    enrol into the class they teach."""
    from apps.schoolsetup.models import AcademicYear, Term

    school = request.school
    term = None
    if data.get("term"):
        term = Term.objects.filter(school=school, pk=data["term"]).first()
        if term is None:
            raise BusinessRuleError({"term": "Unknown term."})
    elif data.get("academic_year"):
        year = AcademicYear.objects.filter(school=school, pk=data["academic_year"]).first()
        if year is None:
            raise BusinessRuleError({"academic_year": "Unknown academic year."})
        terms = year.terms.order_by("start_date")
        today = datetime.date.today()
        term = (
            terms.filter(status=Term.Status.OPEN).first()
            or terms.filter(start_date__lte=today, end_date__gte=today).first()
            or terms.filter(start_date__gt=today).first()
            or terms.last()
        )
        if term is None:
            raise BusinessRuleError({"academic_year": "This year has no terms yet."})
    school_class = None
    if data.get("school_class"):
        school_class = SchoolClass.objects.filter(school=school, pk=data["school_class"]).first()
        if school_class is None:
            raise BusinessRuleError({"school_class": "Unknown class."})
    stream = None
    if data.get("stream"):
        stream = Stream.objects.filter(school=school, pk=data["stream"], school_class=school_class).first()
        if stream is None:
            raise BusinessRuleError({"stream": "That stream is not part of the chosen class."})
    scope = class_scope(request.user, school)
    if scope is not None and not has_perm(request, "learners.manage"):
        if school_class is None or school_class.id not in scope:
            raise BusinessRuleError({"school_class": "You can enrol learners only into your own class."})
    return term, school_class, stream


class LearnerViewSet(SchoolViewSet):
    queryset = Learner.objects.select_related("house")
    perms = PERMS
    # Enrolling (one learner, or a class list from Excel) is open to the director, head
    # teacher, DOS and class teachers; editing and exits stay with learners.manage.
    action_perms = {
        "create": "learners.enrol",
        "excel_template": "learners.enrol",
        "import_excel": "learners.enrol",
        "enrol": "learners.enrol",
        "enrol_fields": "learners.enrol",
    }
    module = "learners"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["status", "sex", "residence", "house", "combination", "year_of_entry"]
    search_fields = ["first_name", "last_name", "other_names", "adm_no", "lin"]
    ordering_fields = ["first_name", "last_name", "adm_no", "admitted_on"]
    export_title = "Learners"

    def get_serializer_class(self):
        return s.LearnerCreateSerializer if self.action == "create" else s.LearnerSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        term_id = params.get("term")
        term = current_term(self.request.school) if not term_id else None
        enrolments = (
            Enrolment.objects.filter(term_id=term_id) if term_id else Enrolment.objects.filter(term=term)
        )
        if params.get("school_class") or params.get("stream"):
            if params.get("school_class"):
                enrolments = enrolments.filter(school_class_id=params["school_class"])
            if params.get("stream"):
                enrolments = enrolments.filter(stream_id=params["stream"])
            queryset = queryset.filter(pk__in=enrolments.values("learner_id"))
        scope = class_scope(self.request.user, self.request.school)
        if scope is not None and not has_perm(self.request, "health.view"):
            in_scope = Enrolment.objects.filter(
                term=term or current_term(self.request.school), school_class_id__in=scope
            )
            queryset = queryset.filter(pk__in=in_scope.values("learner_id"))
        return queryset

    def retrieve(self, request, *args, **kwargs):
        learner = self.get_object()
        if has_perm(request, "health.view") and (learner.allergies or learner.medical_notes):
            log_access(request.school, "learner.health", learner.pk)
        return Response(self.get_serializer(learner).data)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        term, school_class, stream = enrolment_target(
            self.request,
            {
                "term": data.pop("term", None),
                "academic_year": data.pop("academic_year", None),
                "school_class": data.pop("school_class", None),
                "stream": data.pop("stream", None),
            },
        )
        guardian = find_or_create_guardian(
            self.request.school, data.pop("guardian_name", ""), data.pop("guardian_phone", "")
        )
        relationship = data.pop("guardian_relationship", "")
        serializer.instance = admit_learner(
            self.request.school,
            data,
            term=term,
            school_class=school_class,
            stream=stream,
            guardian=guardian,
            relationship=relationship,
        )

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def import_csv(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            raise BusinessRuleError({"file": "Attach a CSV file."})
        return Response(import_learners_csv(request.school, upload))

    @action(detail=False, methods=["get"], url_path="excel-template")
    def excel_template(self, request):
        """The Excel template for bulk enrolment: names, residence, parents, health."""
        response = HttpResponse(
            build_template(request.school.name),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="learner-enrolment-template.xlsx"'
        return response

    @action(
        detail=False, methods=["post"], url_path="import-excel", parser_classes=[MultiPartParser, FormParser]
    )
    def import_excel(self, request):
        """Enrol learners from the filled template into the chosen academic year (or term),
        class and optional stream. Admission numbers are generated for rows without one.
        Send dry_run=true first to check the file without saving anything."""
        upload = request.FILES.get("file")
        term, school_class, stream = enrolment_target(request, request.data)
        missing = [
            name
            for name, value in (("file", upload), ("academic_year", term), ("school_class", school_class))
            if not value
        ]
        if missing:
            raise BusinessRuleError({name: "Required." for name in missing})
        dry_run = str(request.data.get("dry_run", "")).lower() in ("1", "true", "yes")
        try:
            return Response(
                import_learners(request.school, upload, term, school_class, stream, dry_run=dry_run)
            )
        except (OSError, KeyError, ValueError) as exc:
            raise BusinessRuleError({"file": f"The file could not be read ({exc}). Use the Excel template."})

    @action(detail=False, methods=["get"], url_path="enrol-fields")
    def enrol_fields(self, request):
        """The enrolment form's fields: the same columns as the Excel template."""
        return Response(
            [
                {"name": key, "label": header, "required": required, "help": help_text}
                for key, header, required, _width, help_text in COLUMNS
            ]
        )

    @action(detail=False, methods=["post"])
    def enrol(self, request):
        """Enrol one learner with the same details as a row of the Excel template, into the
        chosen academic year (or term), class and stream. The admission number is generated
        when left empty."""
        term, school_class, stream = enrolment_target(request, request.data)
        if school_class is None:
            raise BusinessRuleError({"school_class": "Choose the class."})
        term = term or current_term(request.school)
        if term is None:
            raise BusinessRuleError({"academic_year": "No academic year or term is set up yet."})
        row = {key: request.data.get(key) for key, *_ in COLUMNS}
        try:
            data = validate_row(request.school, row, set())
        except ValueError as exc:
            raise BusinessRuleError({"detail": str(exc)[:1].upper() + str(exc)[1:] + "."})
        learner = create_learner(
            request.school, data, row, term, school_class, stream, term.academic_year.name
        )
        return Response(
            {
                "id": learner.id,
                "adm_no": learner.adm_no,
                "name": learner.full_name,
                "class": str(stream or school_class),
            },
            status=201,
        )

    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request):
        response = HttpResponse(",".join(IMPORT_COLUMNS) + "\n", content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="learners-import-template.csv"'
        return response

    @action(detail=True, methods=["post"], url_path="change-stream")
    def change_stream(self, request, pk=None):
        """Mid-year class or stream change with a logged reason."""
        learner = self.get_object()
        term = current_term(request.school)
        enrolment = Enrolment.objects.filter(learner=learner, term=term).first()
        if enrolment is None:
            raise BusinessRuleError({"detail": "The learner is not enrolled this term."})
        to_class = SchoolClass.objects.filter(school=request.school, pk=request.data.get("to_class")).first()
        to_stream = Stream.objects.filter(school=request.school, pk=request.data.get("to_stream")).first()
        if to_class is None or not request.data.get("reason"):
            raise BusinessRuleError({"detail": "Give the new class and a reason."})
        if to_stream and to_stream.school_class_id != to_class.id:
            raise BusinessRuleError({"to_stream": "The stream must belong to the new class."})
        with transaction.atomic():
            StreamChange.objects.create(
                school=request.school,
                learner=learner,
                term=term,
                from_class=enrolment.school_class,
                from_stream=enrolment.stream,
                to_class=to_class,
                to_stream=to_stream,
                reason=request.data["reason"],
            )
            enrolment.school_class, enrolment.stream = to_class, to_stream
            enrolment.save()
        return Response(s.EnrolmentSerializer(enrolment).data)

    @action(detail=True, methods=["get"])
    def profile(self, request, pk=None):
        """The 360° profile: header, every tab the viewer's role allows, and analytics."""
        from apps.dashboard.profile import build_profile

        return Response(build_profile(request, self.get_object()))

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Fast type-ahead search: names (any order, partial), admission number, LIN,
        class, or a guardian's name or phone. Includes former learners."""
        from apps.dashboard.search import search_learners

        return Response(search_learners(request, request.query_params.get("q", ""), limit=20))


class GuardianViewSet(SchoolViewSet):
    queryset = Guardian.objects.prefetch_related(
        Prefetch("learner_links", queryset=LearnerGuardian.objects.select_related("learner"))
    )
    serializer_class = s.GuardianSerializer
    perms = PERMS
    module = "learners"
    search_fields = ["full_name", "phone", "alt_phone", "email"]


class LearnerGuardianViewSet(SchoolViewSet):
    queryset = LearnerGuardian.objects.select_related("guardian")
    serializer_class = s.LearnerGuardianSerializer
    perms = PERMS
    module = "learners"
    filterset_fields = ["learner", "guardian"]


class EnrolmentViewSet(SchoolViewSet):
    queryset = Enrolment.objects.select_related("school_class", "stream", "term")
    serializer_class = s.EnrolmentSerializer
    perms = PERMS
    module = "learners"
    filterset_fields = ["learner", "term", "school_class", "stream"]

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        """Enrol many learners into a class for a term (e.g. at the start of term)."""
        term_id, class_id = request.data.get("term"), request.data.get("school_class")
        stream_id = request.data.get("stream")
        learner_ids = request.data.get("learners", [])
        created = 0
        for learner in Learner.objects.filter(school=request.school, pk__in=learner_ids):
            _, made = Enrolment.objects.update_or_create(
                school=request.school,
                learner=learner,
                term_id=term_id,
                defaults={
                    "school_class_id": class_id,
                    "stream_id": stream_id,
                    "residence": learner.residence,
                },
            )
            created += int(made)
        return Response({"enrolled": len(learner_ids), "new": created})


class SubjectEnrolmentViewSet(SchoolViewSet):
    queryset = SubjectEnrolment.objects.select_related("subject")
    serializer_class = s.SubjectEnrolmentSerializer
    perms = PERMS
    module = "learners"
    filterset_fields = ["learner", "subject", "academic_year"]


class LearnerDocumentViewSet(SchoolViewSet):
    queryset = LearnerDocument.objects.all()
    serializer_class = s.LearnerDocumentSerializer
    perms = PERMS
    module = "learners"
    filterset_fields = ["learner"]


class LearnerExitViewSet(SchoolViewSet):
    queryset = LearnerExit.objects.select_related("learner")
    serializer_class = s.LearnerExitSerializer
    perms = PERMS
    module = "learners"
    filterset_fields = ["kind", "learner"]


class StreamChangeViewSet(SchoolViewSet):
    queryset = StreamChange.objects.all()
    serializer_class = s.StreamChangeSerializer
    perms = {"read": "learners.view", "write": "learners.manage"}
    module = "learners"
    http_method_names = ["get"]
    filterset_fields = ["learner", "term"]
