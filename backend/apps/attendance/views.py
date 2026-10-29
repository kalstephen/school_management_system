import datetime

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services import class_scope
from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import SchoolPermission
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolReadOnlyViewSet
from apps.learners.services import learners_in
from apps.schoolsetup.calendar import calendar_days, is_school_day
from apps.schoolsetup.models import SchoolClass, Stream, Term, current_term

from .models import AttendanceRecord, AttendanceSession
from .services import class_summary, save_roll_call


class AttendanceRecordSerializer(SchoolOwnedSerializer):
    learner_name = LabelField("learner.full_name")
    date = serializers.DateField(source="session.date", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ["id", "session", "date", "learner", "learner_name", "status", "reason", "version"]


class AttendanceSessionSerializer(SchoolOwnedSerializer):
    class_label = serializers.SerializerMethodField()
    present = serializers.SerializerMethodField()
    absent = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = [
            "id",
            "term",
            "date",
            "school_class",
            "stream",
            "class_label",
            "slot",
            "taken_by",
            "present",
            "absent",
        ]

    def get_class_label(self, obj):
        return str(obj.stream or obj.school_class)

    def get_present(self, obj):
        return obj.records.filter(status__in=("present", "late")).count()

    def get_absent(self, obj):
        return obj.records.filter(status="absent").count()


class ScopedAttendanceView(APIView):
    permission_classes = [IsAuthenticated, SchoolPermission]
    module = "attendance"

    def get_required_perm(self, request):
        return "attendance.view" if request.method == "GET" else "attendance.take"

    def resolve(self, data):
        school = self.request.school
        school_class = SchoolClass.objects.filter(school=school, pk=data.get("school_class")).first()
        if school_class is None:
            raise BusinessRuleError({"school_class": "Choose a class."})
        stream = None
        if data.get("stream"):
            stream = Stream.objects.filter(
                school=school, pk=data["stream"], school_class=school_class
            ).first()
            if stream is None:
                raise BusinessRuleError({"stream": "Unknown stream for this class."})
        scope = class_scope(self.request.user, school)
        if scope is not None and school_class.id not in scope:
            raise BusinessRuleError({"detail": "You are not assigned to this class."})
        date = datetime.date.fromisoformat(data["date"]) if data.get("date") else datetime.date.today()
        # The register belongs to the term the date falls in; outside any term, the current one.
        term = Term.objects.filter(
            school=school, start_date__lte=date, end_date__gte=date
        ).first() or current_term(school)
        if term is None:
            raise BusinessRuleError({"detail": "No term is set up yet."})
        return term, school_class, stream, date


class RollCallView(ScopedAttendanceView):
    """GET: the register for a class (and lesson) on a date, pre-filled with saved marks.
    POST: save it. Designed for a phone: one request loads, one request saves."""

    def get(self, request):
        term, school_class, stream, date = self.resolve(request.query_params)
        slot_id = request.query_params.get("slot") or None
        session = AttendanceSession.objects.filter(
            school=request.school, school_class=school_class, stream=stream, date=date, slot_id=slot_id
        ).first()
        saved = {r.learner_id: r for r in session.records.all()} if session else {}
        learners = learners_in(request.school, term, school_class, stream).order_by("first_name", "last_name")
        school_day, reason = is_school_day(request.school, date)
        return Response(
            {
                "session": session.id if session else None,
                "date": date,
                "term": term.id,
                "school_day": school_day,
                "not_school_reason": reason,
                "class_label": str(stream or school_class),
                "learners": [
                    {
                        "learner": l.id,
                        "name": l.full_name,
                        "adm_no": l.adm_no,
                        "photo": l.photo.url if l.photo else None,
                        "status": saved[l.id].status if l.id in saved else None,
                        "reason": saved[l.id].reason if l.id in saved else "",
                        "version": saved[l.id].version if l.id in saved else 0,
                    }
                    for l in learners
                ],
            }
        )

    def post(self, request):
        term, school_class, stream, date = self.resolve(request.data)
        if date > datetime.date.today():
            raise BusinessRuleError({"date": "Attendance cannot be taken for a future date."})
        school_day, reason = is_school_day(request.school, date)
        if not school_day:
            raise BusinessRuleError({"date": f"No register on {date:%a %d %b}: {reason}."})
        slot = None
        if request.data.get("slot"):
            from apps.timetable.models import TimetableSlot

            slot = TimetableSlot.objects.filter(school=request.school, pk=request.data["slot"]).first()
        session, saved = save_roll_call(
            request.school,
            request.user,
            term,
            date,
            school_class,
            stream,
            request.data.get("records", []),
            slot,
        )
        return Response({"session": session.id, "saved": saved})


class ClassRegisterView(ScopedAttendanceView):
    """The class register for a month (?month=2026-05): one row per learner, one column per
    day, with weekends, public holidays and days between terms greyed out, and the school
    days on which no register was taken."""

    def get(self, request):
        params = request.query_params
        try:
            first = datetime.date.fromisoformat(f"{params.get('month')}-01") if params.get("month") else None
        except ValueError:
            raise BusinessRuleError({"month": "Use the form 2026-05."})
        first = first or datetime.date.today().replace(day=1)
        last = (first + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        term, school_class, stream, _ = self.resolve({**params.dict(), "date": first.isoformat()})
        days = calendar_days(request.school, first, last)
        sessions = {
            s.date: s
            for s in AttendanceSession.objects.filter(
                school=request.school,
                school_class=school_class,
                stream=stream,
                slot__isnull=True,
                date__range=(first, last),
            )
        }
        marks = {}
        for record in AttendanceRecord.objects.filter(session__in=sessions.values()).values(
            "learner_id", "session__date", "status"
        ):
            marks[(record["learner_id"], record["session__date"])] = record["status"]
        terms = Term.objects.filter(school=request.school, start_date__lte=last, end_date__gte=first)
        learner_ids = set()
        for t in terms or [term]:
            learner_ids |= set(
                learners_in(request.school, t, school_class, stream).values_list("id", flat=True)
            )
        from apps.learners.models import Learner

        learners = Learner.objects.filter(pk__in=learner_ids).order_by("first_name", "last_name")
        today = datetime.date.today()
        rows = []
        for learner in learners:
            statuses = {d["date"].isoformat(): marks.get((learner.id, d["date"])) for d in days}
            present = sum(1 for s in statuses.values() if s in ("present", "late"))
            absent = sum(1 for s in statuses.values() if s == "absent")
            rows.append(
                {
                    "learner": learner.id,
                    "name": learner.full_name,
                    "adm_no": learner.adm_no,
                    "days": statuses,
                    "present": present,
                    "absent": absent,
                    "rate": round(100 * present / (present + absent), 1) if present + absent else None,
                }
            )
        school_days = [d for d in days if d["school_day"]]
        return Response(
            {
                "class_label": str(stream or school_class),
                "month": first.strftime("%B %Y"),
                "days": [dict(d, taken=d["date"] in sessions, past=d["date"] <= today) for d in days],
                "school_days": len(school_days),
                "registers_taken": sum(1 for d in school_days if d["date"] in sessions),
                "missing": [
                    d["date"] for d in school_days if d["date"] <= today and d["date"] not in sessions
                ],
                "learners": rows,
            }
        )


class AttendanceSummaryView(ScopedAttendanceView):
    def get(self, request):
        term, school_class, stream, _ = self.resolve(request.query_params)
        return Response(class_summary(request.school, term, school_class, stream))


class AttendanceSessionViewSet(SchoolReadOnlyViewSet):
    queryset = AttendanceSession.objects.select_related("school_class", "stream")
    serializer_class = AttendanceSessionSerializer
    perms = {"read": "attendance.view"}
    module = "attendance"
    filterset_fields = {
        "date": ["exact", "gte", "lte"],
        "school_class": ["exact"],
        "stream": ["exact"],
        "term": ["exact"],
    }


class AttendanceRecordViewSet(SchoolReadOnlyViewSet):
    queryset = AttendanceRecord.objects.select_related("learner", "session")
    serializer_class = AttendanceRecordSerializer
    perms = {"read": "attendance.view"}
    module = "attendance"
    filterset_fields = {
        "learner": ["exact"],
        "status": ["exact"],
        "session__date": ["gte", "lte"],
        "session__term": ["exact"],
    }
