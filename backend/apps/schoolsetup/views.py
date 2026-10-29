import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.roles import PLATFORM_ONLY
from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import SchoolPermission, has_perm
from apps.core.viewsets import SchoolViewSet

from . import serializers as s
from .calendar import calendar_days, generate_year, public_holidays
from .defaults import GRADING_PRESETS, seed_school_defaults
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
    current_term,
)

# Setup is done in the owner console (requests with X-Setup-School, see platform_setup);
# schools read it. Lists every staff member needs (class and term pickers) need only
# dashboard.view.
SETUP_PERMS = {"read": "setup.view", "write": PLATFORM_ONLY}
SHARED_PERMS = {"read": "dashboard.view", "write": PLATFORM_ONLY}


class SchoolProfileView(APIView):
    permission_classes = [IsAuthenticated, SchoolPermission]
    platform_setup = True

    def get_required_perm(self, request):
        return "dashboard.view" if request.method == "GET" else PLATFORM_ONLY

    def get(self, request):
        return Response(s.SchoolProfileSerializer(request.school).data)

    def patch(self, request):
        serializer = s.SchoolProfileSerializer(request.school, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ReportPreviewView(APIView):
    """A sample report card in the school's design, or in a colour being tried out (?color=)."""

    permission_classes = [IsAuthenticated, SchoolPermission]
    platform_setup = "read"

    def get_required_perm(self, request):
        return "setup.view"

    def get(self, request):
        from apps.assessment.pdf import TEMPLATES, render_cards, sample_card

        if request.query_params.get("list"):
            return Response([{"key": k, "label": v} for k, v in TEMPLATES.items()])
        # Schools can try colours; the design itself is agreed with the platform team.
        pdf = render_cards([sample_card(request.school)], None, request.query_params.get("color"))
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="report-preview.pdf"'
        return response


class CurrentTermView(APIView):
    permission_classes = [IsAuthenticated, SchoolPermission]
    platform_setup = "read"

    def get_required_perm(self, request):
        return "dashboard.view"

    def get(self, request):
        term = current_term(request.school)
        return Response(s.TermSerializer(term).data if term else None)


class SeedDefaultsView(APIView):
    """One-click setup: Ugandan sections, classes, NCDC subjects and grading scales."""

    permission_classes = [IsAuthenticated, SchoolPermission]
    platform_setup = True

    def get_required_perm(self, request):
        return PLATFORM_ONLY

    def post(self, request):
        levels = request.data.get("levels") or ["nursery", "primary", "olevel", "alevel"]
        created = seed_school_defaults(request.school, levels)
        return Response(created)


class GenerateYearView(APIView):
    """Create an academic year with its three terms on the standard Ugandan dates, and open
    the term running today. Existing terms are kept; any date can be adjusted afterwards."""

    permission_classes = [IsAuthenticated, SchoolPermission]
    platform_setup = True

    def get_required_perm(self, request):
        return PLATFORM_ONLY

    def post(self, request):
        try:
            year = int(request.data.get("year"))
        except (TypeError, ValueError):
            raise BusinessRuleError({"year": "Give the year, e.g. 2027."})
        if not 2000 <= year <= 2100:
            raise BusinessRuleError({"year": "Give a year between 2000 and 2100."})
        academic_year, created = generate_year(request.school, year)
        return Response({"year": academic_year.name, "terms_created": created})


class SchoolDaysView(APIView):
    """Which days school is in session (?start=&end=, at most a year apart): weekends,
    Uganda public holidays, days between terms and school closures are not school days."""

    permission_classes = [IsAuthenticated, SchoolPermission]
    platform_setup = "read"

    def get_required_perm(self, request):
        return "dashboard.view"

    def get(self, request):
        today = datetime.date.today()
        params = request.query_params
        try:
            start = datetime.date.fromisoformat(params.get("start") or today.replace(day=1).isoformat())
            end = datetime.date.fromisoformat(params.get("end") or start.isoformat())
        except ValueError:
            raise BusinessRuleError({"start": "Use dates like 2026-05-04."})
        if end < start or (end - start).days > 370:
            raise BusinessRuleError({"end": "Choose an end date up to a year after the start."})
        holidays = {}
        for year in range(start.year, end.year + 1):
            holidays.update(public_holidays(year))
        return Response(
            {
                "days": calendar_days(request.school, start, end),
                "public_holidays": [{"date": d, "name": n} for d, n in holidays.items()],
            }
        )


class ClassTeachersView(APIView):
    """GET: every class and stream with its class teacher and deputy.
    POST {target: "class:12" | "stream:5", post: "class_teacher" | "deputy", staff: id | null}:
    appoint, switch or remove. The DOS, head teacher, director and school administrator."""

    permission_classes = [IsAuthenticated, SchoolPermission]

    def get_required_perm(self, request):
        return "dashboard.view" if request.method == "GET" else "classes.assign"

    def get(self, request):
        from .class_teachers import targets

        return Response(targets(request.school))

    def post(self, request):
        from apps.staff.models import StaffProfile

        from .class_teachers import assign, parse_target, targets

        target = parse_target(request.school, request.data.get("target"))
        if target is None:
            raise BusinessRuleError({"target": "Choose a class or stream."})
        staff = None
        if request.data.get("staff"):
            staff = StaffProfile.objects.filter(school=request.school, pk=request.data["staff"]).first()
            if staff is None:
                raise BusinessRuleError({"staff": "Choose a teacher from the staff list."})
        assign(target, request.data.get("post", "class_teacher"), staff, request.user)
        return Response(targets(request.school))


class AcademicYearViewSet(SchoolViewSet):
    platform_setup = True
    queryset = AcademicYear.objects.all()
    serializer_class = s.AcademicYearSerializer
    perms = SHARED_PERMS


class TermViewSet(SchoolViewSet):
    platform_setup = True
    queryset = Term.objects.select_related("academic_year")
    serializer_class = s.TermSerializer
    perms = SHARED_PERMS
    filterset_fields = ["academic_year", "status", "number"]


class SectionViewSet(SchoolViewSet):
    platform_setup = True
    queryset = Section.objects.all()
    serializer_class = s.SectionSerializer
    perms = SHARED_PERMS


class SchoolClassViewSet(SchoolViewSet):
    platform_setup = True
    queryset = SchoolClass.objects.select_related("section").prefetch_related("streams")
    serializer_class = s.SchoolClassSerializer
    perms = SHARED_PERMS
    action_perms = {"class_teacher": "classes.assign"}
    filterset_fields = ["section", "is_candidate_class"]

    @action(detail=True, methods=["post"], url_path="class-teacher")
    def class_teacher(self, request, pk=None):
        """The school chooses who teaches the class (the class itself is set up centrally):
        {"class_teacher": id | null} and/or {"deputy_class_teacher": id | null}."""
        from apps.staff.models import StaffProfile

        from .class_teachers import assign

        school_class = self.get_object()
        for key, post in (("class_teacher", "class_teacher"), ("deputy_class_teacher", "deputy")):
            if key not in request.data:
                continue
            teacher = None
            if request.data.get(key):
                teacher = StaffProfile.objects.filter(school=request.school, pk=request.data[key]).first()
                if teacher is None:
                    raise BusinessRuleError({key: "Choose a teacher from the staff list."})
            assign(school_class, post, teacher, request.user)
            school_class.refresh_from_db()
        return Response(self.get_serializer(school_class).data)


class StreamViewSet(SchoolViewSet):
    platform_setup = True
    queryset = Stream.objects.select_related("school_class")
    serializer_class = s.StreamSerializer
    perms = SHARED_PERMS
    filterset_fields = ["school_class"]


class HouseViewSet(SchoolViewSet):
    platform_setup = True
    queryset = House.objects.all()
    serializer_class = s.HouseSerializer
    perms = SHARED_PERMS


class DepartmentViewSet(SchoolViewSet):
    platform_setup = True
    queryset = Department.objects.all()
    serializer_class = s.DepartmentSerializer
    perms = SHARED_PERMS


class ClubViewSet(SchoolViewSet):
    platform_setup = True
    queryset = Club.objects.all()
    serializer_class = s.ClubSerializer
    perms = SHARED_PERMS


class GradingEditMixin:
    """The owner console loads the standard Ugandan scales; the school can then change the
    cut-offs and add grades: the head teacher or director (setup.manage) and the Director of
    Studies (assessment.manage)."""

    def get_required_perm(self, request):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return "dashboard.view"
        return "assessment.manage" if has_perm(request, "assessment.manage") else "setup.manage"


class GradingScaleViewSet(GradingEditMixin, SchoolViewSet):
    platform_setup = True
    queryset = GradingScale.objects.prefetch_related("bands")
    serializer_class = s.GradingScaleSerializer
    perms = SETUP_PERMS

    @action(detail=False, methods=["get"])
    def presets(self, request):
        """The standard Ugandan scales a school can start from."""
        return Response(
            [
                {
                    "key": key,
                    "name": preset["name"],
                    "description": preset["description"],
                    "bands": [
                        {
                            "label": b[0],
                            "min_score": b[1],
                            "max_score": b[2],
                            "points": b[3],
                            "descriptor": b[4],
                        }
                        for b in preset["bands"]
                    ],
                }
                for key, preset in GRADING_PRESETS.items()
            ]
        )

    @action(detail=True, methods=["post"], url_path="set-bands")
    def set_bands(self, request, pk=None):
        """Replace the scale's bands in one go, after checking they make sense:
        no overlaps, no gaps, the whole 0–100 range covered and every grade named once."""
        scale = self.get_object()
        if request.data.get("preset"):
            preset = GRADING_PRESETS.get(request.data["preset"])
            if preset is None:
                raise BusinessRuleError({"preset": "Unknown preset."})
            rows = [
                {"label": b[0], "min_score": b[1], "max_score": b[2], "points": b[3], "descriptor": b[4]}
                for b in preset["bands"]
            ]
        else:
            rows = request.data.get("bands") or []
        bands = validate_bands(rows)
        with transaction.atomic():
            scale.bands.all().delete()
            for band in bands:
                GradeBand.objects.create(school=scale.school, scale=scale, **band)
        if request.data.get("name"):
            scale.name = request.data["name"]
            scale.save()
        return Response(s.GradingScaleSerializer(GradingScale.objects.get(pk=scale.pk)).data)


def validate_bands(rows):
    """Check a list of grade bands and return them cleaned, highest first."""
    errors, bands = [], []
    for index, row in enumerate(rows, start=1):
        label = str(row.get("label") or "").strip()
        try:
            low, high = Decimal(str(row.get("min_score"))), Decimal(str(row.get("max_score")))
            points = Decimal(str(row.get("points") or 0))
        except (InvalidOperation, TypeError):
            errors.append(f"Row {index}: the marks and points must be numbers.")
            continue
        if not label:
            errors.append(f"Row {index}: give the grade a name, e.g. D1.")
        if low > high:
            errors.append(f"Row {index} ({label}): 'from' must not be above 'to'.")
        if low < 0 or high > 100:
            errors.append(f"Row {index} ({label}): marks must be between 0 and 100.")
        bands.append(
            {
                "label": label,
                "min_score": low,
                "max_score": high,
                "points": points,
                "descriptor": str(row.get("descriptor") or "")[:200],
            }
        )
    if not bands:
        errors.append("Add at least one grade.")
    labels = [b["label"].lower() for b in bands]
    if len(set(labels)) != len(labels):
        errors.append("Each grade name must be used once.")
    ordered = sorted(bands, key=lambda b: b["min_score"])
    if ordered and not errors:
        if ordered[0]["min_score"] != 0:
            errors.append(f"The lowest grade must start at 0 (it starts at {ordered[0]['min_score']}).")
        if ordered[-1]["max_score"] != 100:
            errors.append(f"The highest grade must end at 100 (it ends at {ordered[-1]['max_score']}).")
        for lower, upper in zip(ordered, ordered[1:], strict=False):
            if upper["min_score"] <= lower["max_score"]:
                errors.append(f"{lower['label']} and {upper['label']} overlap.")
            elif upper["min_score"] - lower["max_score"] > Decimal("1"):
                errors.append(
                    f"There is a gap between {lower['label']} (to {lower['max_score']}) "
                    f"and {upper['label']} (from {upper['min_score']})."
                )
    if errors:
        raise BusinessRuleError({"bands": errors})
    return sorted(bands, key=lambda b: -b["min_score"])


class GradeBandViewSet(GradingEditMixin, SchoolViewSet):
    platform_setup = True
    queryset = GradeBand.objects.all()
    serializer_class = s.GradeBandSerializer
    perms = SETUP_PERMS
    filterset_fields = ["scale"]


class CalendarEventViewSet(SchoolViewSet):
    platform_setup = True
    queryset = CalendarEvent.objects.all()
    serializer_class = s.CalendarEventSerializer
    perms = {"read": "dashboard.view", "write": "communication.post"}
    filterset_fields = ["kind"]
    module = "communication"
