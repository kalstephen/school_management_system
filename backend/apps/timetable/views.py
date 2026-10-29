import datetime

from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import has_perm
from apps.core.serializers import LabelField, SchoolOwnedSerializer
from apps.core.viewsets import SchoolViewSet
from apps.schoolsetup.models import Term

from .models import Period, Room, Substitution, TimetableSlot
from .services import find_clashes, free_teachers, generate_timetable

PERMS = {"read": "timetable.view", "write": "timetable.manage"}


class PeriodSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Period
        fields = ["id", "name", "start_time", "end_time", "order", "is_break"]


class RoomSerializer(SchoolOwnedSerializer):
    class Meta:
        model = Room
        fields = ["id", "name", "capacity", "kind"]


class SlotSerializer(SchoolOwnedSerializer):
    subject_name = LabelField("subject.name")
    teacher_name = LabelField("teacher.full_name", default=None)
    room_name = LabelField("room.name", default=None)
    class_label = serializers.SerializerMethodField()
    period_name = LabelField("period.name")

    class Meta:
        model = TimetableSlot
        fields = [
            "id",
            "term",
            "day",
            "period",
            "period_name",
            "school_class",
            "stream",
            "class_label",
            "subject",
            "subject_name",
            "teacher",
            "teacher_name",
            "room",
            "room_name",
        ]

    def get_class_label(self, obj):
        return str(obj.stream or obj.school_class)

    def validate(self, attrs):
        get = lambda k: attrs.get(k, getattr(self.instance, k, None))  # noqa: E731
        clashes = find_clashes(
            self.context["request"].school,
            get("term"),
            get("day"),
            get("period"),
            get("school_class"),
            get("stream"),
            get("teacher"),
            get("room"),
            exclude_pk=getattr(self.instance, "pk", None),
        )
        if clashes:
            raise serializers.ValidationError({"clashes": clashes})
        return attrs


class SubstitutionSerializer(SchoolOwnedSerializer):
    substitute_name = LabelField("substitute.full_name")
    slot_detail = SlotSerializer(source="slot", read_only=True)

    class Meta:
        model = Substitution
        fields = ["id", "slot", "slot_detail", "date", "substitute", "substitute_name", "reason"]


class PeriodViewSet(SchoolViewSet):
    queryset = Period.objects.all()
    serializer_class = PeriodSerializer
    perms = PERMS
    module = "timetable"


class RoomViewSet(SchoolViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    perms = PERMS
    module = "timetable"


class SlotViewSet(SchoolViewSet):
    queryset = TimetableSlot.objects.select_related(
        "subject", "teacher", "room", "period", "school_class", "stream"
    )
    serializer_class = SlotSerializer
    perms = PERMS
    module = "timetable"
    pagination_class = None
    filterset_fields = ["term", "school_class", "stream", "teacher", "room", "day"]
    action_perms = {
        "publish": "timetable.manage",
        "unpublish": "timetable.manage",
        "status": "timetable.view",
        "pdf": "timetable.view",
    }

    def get_queryset(self):
        """The DOS (timetable.manage) works on drafts; everyone else sees a term's timetable
        only after it is published. ?mine=1 gives the signed-in teacher's own lessons."""
        queryset = super().get_queryset()
        if not has_perm(self.request, "timetable.manage"):
            queryset = queryset.filter(term__timetable_published_at__isnull=False)
        if self.request.query_params.get("mine"):
            queryset = queryset.filter(teacher__user=self.request.user)
        return queryset

    def _term(self, request, source):
        term = Term.objects.filter(school=request.school, pk=source.get("term")).first()
        if term is None:
            raise BusinessRuleError({"term": "Choose a term."})
        return term

    @action(detail=False, methods=["get"])
    def status(self, request):
        term = self._term(request, request.query_params)
        return Response(
            {
                "term": term.id,
                "published": term.timetable_published_at is not None,
                "published_at": term.timetable_published_at,
                "published_by": term.timetable_published_by.display_name
                if term.timetable_published_by
                else None,
                "lessons": TimetableSlot.objects.filter(school=request.school, term=term).count(),
            }
        )

    @action(detail=False, methods=["post"])
    def publish(self, request):
        """Make the term's timetable visible to every teacher, and tell them."""
        from apps.accounts.models import Membership
        from apps.communication.services import notify

        term = self._term(request, request.data)
        if not TimetableSlot.objects.filter(school=request.school, term=term).exists():
            raise BusinessRuleError({"detail": "The timetable has no lessons yet."})
        term.timetable_published_at, term.timetable_published_by = timezone.now(), request.user
        term.save()
        users = [
            m.user
            for m in Membership.objects.filter(school=request.school, is_active=True).select_related("user")
        ]
        notify(
            request.school,
            users,
            "Timetable published",
            f"The {term} timetable is ready. Open Timetable to see it.",
            link="/timetable",
        )
        return Response({"published": True, "published_at": term.timetable_published_at})

    @action(detail=False, methods=["post"])
    def unpublish(self, request):
        term = self._term(request, request.data)
        term.timetable_published_at, term.timetable_published_by = None, None
        term.save()
        return Response({"published": False})

    @action(detail=False, methods=["get"])
    def pdf(self, request):
        """A printable week for a class (?school_class=), teacher (?teacher= or ?mine=1) or room (?room=)."""
        from apps.schoolsetup.models import SchoolClass, Stream
        from apps.staff.models import StaffProfile

        from .pdf import weekly_timetable_pdf

        params = request.query_params
        term = self._term(request, params)
        slots = self.filter_queryset(self.get_queryset()).filter(term=term)
        extra = ""
        if params.get("school_class"):
            target = (
                Stream.objects.filter(pk=params.get("stream")).first()
                or SchoolClass.objects.filter(school=request.school, pk=params["school_class"]).first()
            )
            kind = "Class timetable"
            lead = getattr(target, "class_teacher", None)
            deputy = getattr(target, "deputy_class_teacher", None)
            if lead or deputy:
                extra = " · Class teacher: " + (lead.full_name if lead else "–")
                extra += f" · Deputy: {deputy.full_name}" if deputy else ""
        elif params.get("teacher") or params.get("mine"):
            target = (
                StaffProfile.objects.filter(school=request.school, pk=params.get("teacher")).first()
                or StaffProfile.objects.filter(school=request.school, user=request.user).first()
            )
            kind = "Teacher's timetable"
        elif params.get("room"):
            target, kind = (
                Room.objects.filter(school=request.school, pk=params["room"]).first(),
                "Room timetable",
            )
        else:
            raise BusinessRuleError({"detail": "Choose a class, teacher or room."})
        periods = Period.objects.filter(school=request.school).order_by("order")
        status_note = "" if term.timetable_published_at else " · DRAFT (not yet published)"
        content = weekly_timetable_pdf(
            request.school, f"{kind} — {target}", f"{term}{extra}{status_note}", periods, slots
        )
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="timetable-{slugify(str(target))}.pdf"'
        return response

    @action(detail=False, methods=["post"])
    def generate(self, request):
        term = Term.objects.filter(school=request.school, pk=request.data.get("term")).first()
        if term is None:
            raise BusinessRuleError({"term": "Choose a term."})
        return Response(generate_timetable(request.school, term, request.data.get("classes") or None))

    @action(detail=False, methods=["get"], url_path="free-teachers")
    def free_teachers(self, request):
        params = request.query_params
        term = Term.objects.filter(school=request.school, pk=params.get("term")).first()
        if term is None:
            raise BusinessRuleError({"term": "Choose a term."})
        on_date = (
            datetime.date.fromisoformat(params.get("date")) if params.get("date") else datetime.date.today()
        )
        teachers = free_teachers(
            request.school, term, int(params.get("day", on_date.isoweekday())), params.get("period"), on_date
        )
        return Response([{"id": t.id, "name": t.full_name} for t in teachers])


class SubstitutionViewSet(SchoolViewSet):
    queryset = Substitution.objects.select_related("substitute", "slot__subject", "slot__period")
    serializer_class = SubstitutionSerializer
    perms = PERMS
    module = "timetable"
    filterset_fields = {"date": ["exact", "gte", "lte"], "substitute": ["exact"]}
