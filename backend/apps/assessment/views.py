from collections import defaultdict
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services import SCHOOL_WIDE_ROLES, can_enter_marks, class_scope, user_roles
from apps.core.exceptions import BusinessRuleError
from apps.core.models import AuditLog
from apps.core.permissions import SchoolPermission, has_perm
from apps.core.viewsets import SchoolReadOnlyViewSet, SchoolViewSet
from apps.schoolsetup.models import SchoolClass, Term

from . import serializers as s
from . import services
from .grading import compute_class_results
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
from .pdf import render_cards
from .reports import generate_report_cards, publish
from .uneb import analyse, import_results

MODULE = "assessment"


def _term_and_class(request, data):
    term = Term.objects.filter(school=request.school, pk=data.get("term")).first()
    school_class = SchoolClass.objects.filter(school=request.school, pk=data.get("school_class")).first()
    if term is None or school_class is None:
        raise BusinessRuleError({"detail": "Choose a term and a class."})
    scope = class_scope(request.user, request.school)
    if scope is not None and school_class.id not in scope:
        raise BusinessRuleError({"detail": f"You are not assigned to {school_class}."})
    return term, school_class


class ExamViewSet(SchoolViewSet):
    queryset = Exam.objects.select_related("term__academic_year").prefetch_related("classes")
    serializer_class = s.ExamSerializer
    perms = {"read": "assessment.view", "write": "assessment.manage"}
    module = MODULE
    filterset_fields = ["term", "kind", "classes"]

    action_perms = {
        "publish_schedule": "assessment.manage",
        "unpublish_schedule": "assessment.manage",
        "schedule_pdf": "assessment.view",
        "weights": "assessment.view",
        "prepare_sheets": "assessment.manage",
        "generate_timetable": "assessment.manage",
        "seating": "assessment.view",
        "seating_pdf": "assessment.view",
    }

    @action(detail=True, methods=["post"], url_path="generate-timetable")
    def generate_timetable(self, request, pk=None):
        """Place every paper automatically: {start_date, end_date, sessions: [["08:30","10:30"],…],
        max_per_day, replace}. Existing rows are kept unless replace is true."""
        import datetime

        from .exam_planning import generate_exam_timetable

        exam = self.get_object()
        data = request.data

        def day(key):
            try:
                return datetime.date.fromisoformat(data[key]) if data.get(key) else None
            except ValueError:
                raise BusinessRuleError({key: "Use a date like 2026-11-16."})

        start, end = day("start_date"), day("end_date")
        if start and end and (exam.start_date != start or exam.end_date != end):
            exam.start_date, exam.end_date = start, end
            exam.save(update_fields=["start_date", "end_date"])
        return Response(
            generate_exam_timetable(
                exam,
                start,
                end,
                data.get("sessions") or None,
                data.get("max_per_day", 2),
                bool(data.get("replace")),
            )
        )

    @action(detail=True, methods=["get", "post"])
    def seating(self, request, pk=None):
        """GET: the sessions with how many are seated. POST {rooms: [ids], sessions?: [{date,
        start_time}]}: seat every learner of each session across the rooms, classes mixed."""
        from apps.timetable.models import Room

        from .exam_planning import generate_seating, sessions_of
        from .models import ExamSeat

        exam = self.get_object()
        if request.method == "POST":
            if not has_perm(request, "assessment.manage"):
                raise BusinessRuleError({"detail": "The DOS or head teacher makes the seating plan."})
            ids = request.data.get("rooms") or []
            rooms = list(Room.objects.filter(school=request.school, pk__in=ids).order_by("name"))
            return Response(generate_seating(exam, rooms, request.data.get("sessions")))
        counts = defaultdict(int)
        rooms = defaultdict(set)
        for seat in ExamSeat.objects.filter(exam=exam).select_related("room"):
            counts[(seat.date, seat.start_time)] += 1
            rooms[(seat.date, seat.start_time)].add(seat.room.name)
        return Response(
            [
                {
                    "date": date,
                    "start_time": start.strftime("%H:%M"),
                    "end_time": end.strftime("%H:%M"),
                    "papers": sorted(
                        {str(r.subject) for r in exam.schedule.filter(date=date, start_time=start)}
                    ),
                    "seated": counts[(date, start)],
                    "rooms": sorted(rooms[(date, start)]),
                }
                for date, start, end in sessions_of(exam)
            ]
        )

    @action(detail=True, methods=["get"], url_path="seating-pdf")
    def seating_pdf(self, request, pk=None):
        from apps.timetable.pdf import seating_plan_pdf

        from .models import ExamSeat

        exam = self.get_object()
        seats = ExamSeat.objects.filter(exam=exam).select_related("learner", "room", "school_class")
        if request.query_params.get("date"):
            seats = seats.filter(date=request.query_params["date"])
        if request.query_params.get("start_time"):
            seats = seats.filter(start_time=request.query_params["start_time"])
        response = HttpResponse(
            seating_plan_pdf(request.school, exam, list(seats)), content_type="application/pdf"
        )
        response["Content-Disposition"] = f'inline; filename="seating-plan-{exam.pk}.pdf"'
        return response

    @action(detail=True, methods=["post"], url_path="publish-schedule")
    def publish_schedule(self, request, pk=None):
        """The DOS publishes the exam timetable; teachers then see it and are notified."""
        from apps.accounts.models import Membership
        from apps.communication.services import notify

        exam = self.get_object()
        if not exam.schedule.exists():
            raise BusinessRuleError({"detail": "Add the papers to the exam timetable first."})
        exam.schedule_published_at = timezone.now()
        exam.save()
        users = [
            m.user
            for m in Membership.objects.filter(school=request.school, is_active=True).select_related("user")
        ]
        notify(
            request.school,
            users,
            "Exam timetable published",
            f"The {exam.name} timetable is ready.",
            link="/exams",
        )
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=["post"], url_path="unpublish-schedule")
    def unpublish_schedule(self, request, pk=None):
        exam = self.get_object()
        exam.schedule_published_at = None
        exam.save()
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=["get"], url_path="schedule-pdf")
    def schedule_pdf(self, request, pk=None):
        from apps.timetable.pdf import exam_timetable_pdf

        exam = self.get_object()
        if exam.schedule_published_at is None and not has_perm(request, "assessment.manage"):
            raise BusinessRuleError({"detail": "This exam timetable is not published yet."})
        rows = exam.schedule.select_related(
            "subject", "paper", "school_class", "room", "invigilator"
        ).order_by("date", "start_time", "school_class__order")
        if request.query_params.get("school_class"):
            rows = rows.filter(school_class_id=request.query_params["school_class"])
        response = HttpResponse(
            exam_timetable_pdf(request.school, exam, rows), content_type="application/pdf"
        )
        response["Content-Disposition"] = f'inline; filename="exam-timetable-{exam.pk}.pdf"'
        return response

    @action(detail=False, methods=["get"])
    def weights(self, request):
        """How each class's term score is built: its exams (continuous assessment and final
        papers) and their weights, which should add up to 100%."""
        term = Term.objects.filter(school=request.school, pk=request.query_params.get("term")).first()
        if term is None:
            raise BusinessRuleError({"term": "Choose a term."})
        rows = []
        for school_class in SchoolClass.objects.filter(school=request.school).order_by("order"):
            exams = list(Exam.objects.filter(term=term, classes=school_class).order_by("start_date", "id"))
            if not exams:
                continue
            total = sum(float(e.weight) for e in exams)
            rows.append(
                {
                    "class_id": school_class.id,
                    "class": school_class.name,
                    "total": total,
                    "ok": abs(total - 100) < 0.01,
                    "exams": [
                        {"id": e.id, "name": e.name, "kind": e.kind, "weight": float(e.weight)} for e in exams
                    ],
                }
            )
        return Response(rows)

    @action(detail=True, methods=["post"], url_path="prepare-sheets")
    def prepare_sheets(self, request, pk=None):
        exam = self.get_object()
        classes = SchoolClass.objects.filter(school=request.school, pk__in=request.data.get("classes") or [])
        if not classes:
            classes = exam.classes.all()
        created = sum(services.prepare_sheets(exam, c, bool(request.data.get("by_stream"))) for c in classes)
        return Response({"created": created})


class ExamScheduleViewSet(SchoolViewSet):
    queryset = ExamSchedule.objects.select_related("subject", "invigilator", "room")
    serializer_class = s.ExamScheduleSerializer
    perms = {"read": "assessment.view", "write": "assessment.manage"}
    module = MODULE
    filterset_fields = ["exam", "school_class", "date", "invigilator"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not has_perm(self.request, "assessment.manage"):
            queryset = queryset.filter(exam__schedule_published_at__isnull=False)
        return queryset


class MarkSheetViewSet(SchoolViewSet):
    queryset = MarkSheet.objects.select_related("exam", "subject", "paper", "school_class", "stream")
    serializer_class = s.MarkSheetSerializer
    perms = {"read": "assessment.view", "write": "assessment.manage"}
    action_perms = {
        "entries": "assessment.view",
        "submit": "marks.enter",
        "review": "marks.review",
        "return_sheet": "marks.review",
        "approve": "marks.approve",
        "reopen": "marks.approve",
        "history": "assessment.view",
    }
    module = MODULE
    filterset_fields = ["exam", "exam__term", "subject", "school_class", "stream", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        scope = class_scope(self.request.user, self.request.school)
        if scope is not None:
            queryset = queryset.filter(school_class_id__in=scope)
        if self.request.query_params.get("mine"):
            from apps.accounts.services import class_teacher_classes
            from apps.curriculum.models import SubjectAllocation

            pairs = SubjectAllocation.objects.filter(
                school=self.request.school, teacher__user=self.request.user
            )
            # A class teacher's own class counts as theirs for every subject.
            own = class_teacher_classes(
                self.request.school, list(user_roles(self.request.user, self.request.school))
            )
            ids = [
                sh.id
                for sh in queryset
                if sh.school_class_id in own
                or any(
                    p.subject_id == sh.subject_id and p.school_class_id == sh.school_class_id for p in pairs
                )
            ]
            queryset = queryset.filter(pk__in=ids)
        return queryset.order_by("school_class__order", "subject__order", "subject__name", "id")

    def _check_can_enter(self, sheet):
        if not can_enter_marks(
            self.request.user, self.request.school, sheet.subject_id, sheet.school_class_id
        ):
            raise BusinessRuleError({"detail": "You are not allocated to teach this subject in this class."})

    def _check_hod(self, sheet):
        roles = list(user_roles(self.request.user, self.request.school))
        if any(r.role in SCHOOL_WIDE_ROLES for r in roles):
            return
        departments = {r.scope_id for r in roles if r.role == "hod" and r.scope_type == "department"}
        if sheet.subject.department_id not in departments:
            raise BusinessRuleError({"detail": "Only the head of this subject's department can review it."})

    @action(detail=True, methods=["get", "post"])
    def entries(self, request, pk=None):
        sheet = self.get_object()
        if request.method == "POST":
            if not has_perm(request, "marks.enter"):
                raise BusinessRuleError({"detail": "You cannot enter marks."})
            self._check_can_enter(sheet)
            return Response(services.save_marks(sheet, request.data.get("marks", [])))
        marks = {m.learner_id: m for m in sheet.marks.all()}
        return Response(
            {
                "sheet": s.MarkSheetSerializer(sheet, context={"request": request}).data,
                "max_mark": sheet.exam.max_mark,
                "editable": sheet.is_editable and has_perm(request, "marks.enter"),
                "learners": [
                    {
                        "learner": l.id,
                        "name": l.full_name,
                        "adm_no": l.adm_no,
                        "score": marks[l.id].score if l.id in marks else None,
                        "is_absent": marks[l.id].is_absent if l.id in marks else False,
                        "version": marks[l.id].version if l.id in marks else 0,
                    }
                    for l in services.sheet_learners(sheet)
                ],
            }
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        sheet = self.get_object()
        self._check_can_enter(sheet)
        return Response(self.get_serializer(services.submit(sheet, request.user)).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        sheet = self.get_object()
        self._check_hod(sheet)
        return Response(self.get_serializer(services.review(sheet, request.user)).data)

    @action(detail=True, methods=["post"], url_path="return")
    def return_sheet(self, request, pk=None):
        sheet = self.get_object()
        if not has_perm(request, "marks.approve"):
            self._check_hod(sheet)
        return Response(
            self.get_serializer(
                services.return_sheet(sheet, request.user, request.data.get("comment", ""))
            ).data
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return Response(self.get_serializer(services.approve(self.get_object(), request.user)).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        sheet = services.reopen(self.get_object(), request.user, request.data.get("reason", ""))
        return Response(self.get_serializer(sheet).data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """Edit history for every mark on the sheet (from the audit log)."""
        sheet = self.get_object()
        mark_ids = [str(i) for i in Mark.objects.filter(mark_sheet=sheet).values_list("id", flat=True)]
        logs = AuditLog.objects.filter(
            school=request.school, entity="assessment.mark", object_id__in=mark_ids
        )
        return Response(
            [
                {
                    "mark": log.object_id,
                    "who": log.object_repr,
                    "action": log.action,
                    "changes": log.changes,
                    "user": log.user.username if log.user else None,
                    "at": log.timestamp,
                }
                for log in logs.select_related("user")[:500]
            ]
        )

    @action(detail=False, methods=["post"], url_path="bulk-approve")
    def bulk_approve(self, request):
        if not has_perm(request, "marks.approve"):
            raise BusinessRuleError({"detail": "You cannot approve marks."})
        approved = 0
        for sheet in self.get_queryset().filter(
            pk__in=request.data.get("ids", []), status__in=["submitted", "reviewed"]
        ):
            services.approve(sheet, request.user)
            approved += 1
        return Response({"approved": approved})


class AOIScoreViewSet(SchoolViewSet):
    queryset = AOIScore.objects.select_related("competency")
    serializer_class = s.AOIScoreSerializer
    perms = {"read": "assessment.view", "write": "marks.enter"}
    module = MODULE
    filterset_fields = ["learner", "competency", "term", "competency__subject"]


class NurseryRatingViewSet(SchoolViewSet):
    queryset = NurseryRating.objects.all()
    serializer_class = s.NurseryRatingSerializer
    perms = {"read": "assessment.view", "write": "marks.enter"}
    module = MODULE
    filterset_fields = ["learner", "term", "learning_area"]


class ResultSummaryViewSet(SchoolReadOnlyViewSet):
    queryset = ResultSummary.objects.select_related("learner")
    serializer_class = s.ResultSummarySerializer
    perms = {"read": "assessment.view"}
    action_perms = {"compute": "assessment.manage"}
    module = MODULE
    filterset_fields = ["term", "school_class", "stream", "learner"]
    ordering_fields = ["position", "average", "aggregate"]
    ordering = ["position"]

    @action(detail=False, methods=["post"])
    def compute(self, request):
        """Preview results for a class (unapproved marks included when preview=true)."""
        term, school_class = _term_and_class(request, request.data)
        results = compute_class_results(term, school_class, approved_only=not request.data.get("preview"))
        return Response(s.ResultSummarySerializer(results, many=True).data)


class ReportCardViewSet(SchoolViewSet):
    queryset = ReportCard.objects.select_related("learner", "term__academic_year")
    serializer_class = s.ReportCardSerializer
    perms = {"read": "reports.view", "write": "reports.comment"}
    action_perms = {
        "generate": "reports.generate",
        "publish": "reports.approve",
        "pdf": "reports.view",
        "class_pdf": "reports.view",
        "email": "reports.approve",
    }
    module = MODULE
    http_method_names = ["get", "patch", "post"]
    filterset_fields = ["term", "status", "learner", "result__school_class", "result__stream"]

    def get_queryset(self):
        queryset = super().get_queryset()
        scope = class_scope(self.request.user, self.request.school)
        return queryset if scope is None else queryset.filter(result__school_class_id__in=scope)

    def perform_update(self, serializer):
        card = serializer.instance
        if card.status != ReportCard.Status.DRAFT:
            raise BusinessRuleError({"detail": "Published report cards cannot be changed."})
        if "head_comment" in serializer.validated_data and not has_perm(self.request, "reports.approve"):
            raise BusinessRuleError({"head_comment": "Only the head teacher writes this comment."})
        card = serializer.save()
        card.snapshot["class_teacher_comment"] = card.class_teacher_comment
        card.snapshot["head_comment"] = card.head_comment
        card.save()

    @action(detail=False, methods=["post"])
    def generate(self, request):
        term, school_class = _term_and_class(request, request.data)
        cards = generate_report_cards(
            term, school_class, allow_unapproved=bool(request.data.get("allow_unapproved"))
        )
        return Response({"generated": len(cards)})

    @action(detail=False, methods=["post"])
    def publish(self, request):
        term, school_class = _term_and_class(request, request.data)
        cards = ReportCard.objects.filter(
            school=request.school,
            term=term,
            result__school_class=school_class,
            status=ReportCard.Status.DRAFT,
        )
        if request.data.get("ids"):
            cards = cards.filter(pk__in=request.data["ids"])
        return Response({"published": publish(list(cards), request.user)})

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        card = self.get_object()
        response = HttpResponse(render_cards([card]), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="report-{card.serial}.pdf"'
        return response

    @action(detail=False, methods=["get"], url_path="class-pdf")
    def class_pdf(self, request):
        """All report cards for a class in one PDF, ready for bulk printing."""
        term, school_class = _term_and_class(request, request.query_params)
        cards = (
            ReportCard.objects.filter(school=request.school, term=term, result__school_class=school_class)
            .exclude(status=ReportCard.Status.SUPERSEDED)
            .select_related("learner")
            .order_by("result__stream__name", "learner__first_name")
        )
        response = HttpResponse(render_cards(list(cards)), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="reports-{school_class.name}-T{term.number}.pdf"'
        return response

    @action(detail=False, methods=["post"])
    def email(self, request):
        """Email published report cards (PDF) to guardians who receive email."""
        from apps.communication.services import email_report_cards

        term, school_class = _term_and_class(request, request.data)
        cards = ReportCard.objects.filter(
            school=request.school,
            term=term,
            result__school_class=school_class,
            status=ReportCard.Status.PUBLISHED,
        )
        return Response(email_report_cards(request.school, list(cards)))


class SubjectCommentsView(APIView):
    """GET ?term=&school_class=&subject=[&stream=]: each learner's mark in the subject, the
    preset comment for it and the comment written. POST {term, school_class, subject,
    comments: [{learner, text}]}: save (an empty text removes the comment). Open to whoever
    may enter the subject's marks in that class."""

    permission_classes = [IsAuthenticated, SchoolPermission]
    module = MODULE

    def get_required_perm(self, request):
        return "assessment.view" if request.method == "GET" else "marks.enter"

    def _resolve(self, data):
        from apps.curriculum.models import Subject

        term, school_class = _term_and_class(self.request, data)
        subject = Subject.objects.filter(school=self.request.school, pk=data.get("subject")).first()
        if subject is None:
            raise BusinessRuleError({"subject": "Choose a subject."})
        return term, school_class, subject

    def get(self, request):
        from apps.learners.services import learners_in
        from apps.schoolsetup.models import Stream

        from .grading import term_subject_scores
        from .models import SubjectComment
        from .reports import subject_comment_presets, suggested_subject_comment

        term, school_class, subject = self._resolve(request.query_params)
        stream = Stream.objects.filter(school=request.school, pk=request.query_params.get("stream")).first()
        learners = list(
            learners_in(request.school, term, school_class, stream).order_by("first_name", "last_name")
        )
        scores, _ = term_subject_scores(term, school_class, [l.id for l in learners], approved_only=False)
        written = dict(
            SubjectComment.objects.filter(term=term, subject=subject, learner__in=learners).values_list(
                "learner_id", "text"
            )
        )
        presets = subject_comment_presets(request.school)
        scale = school_class.section.grading_scale
        rows = []
        for learner in learners:
            score = scores.get(learner.id, {}).get(subject.id, {}).get("score")
            band = scale.band_for(Decimal(str(round(score, 2)))) if scale and score is not None else None
            rows.append(
                {
                    "learner": learner.id,
                    "name": learner.full_name,
                    "adm_no": learner.adm_no,
                    "score": None if score is None else round(score, 1),
                    "grade": band.label if band else "",
                    "suggested": suggested_subject_comment(presets, subject.id, score),
                    "comment": written.get(learner.id, ""),
                }
            )
        return Response(
            {
                "editable": has_perm(request, "marks.enter")
                and can_enter_marks(request.user, request.school, subject.id, school_class.id),
                "presets": [
                    {"text": p.text, "min": float(p.min_average), "max": float(p.max_average)}
                    for p in presets
                    if p.subject_id in (None, subject.id)
                ],
                "learners": rows,
            }
        )

    def post(self, request):
        from .models import ReportCard, SubjectComment
        from .reports import subject_comments

        term, school_class, subject = self._resolve(request.data)
        if not can_enter_marks(request.user, request.school, subject.id, school_class.id):
            raise BusinessRuleError({"detail": "You do not teach this subject in this class."})
        saved = 0
        learner_ids = []
        for row in request.data.get("comments", []):
            text = str(row.get("text") or "").strip()[:300]
            learner_id = int(row["learner"])
            learner_ids.append(learner_id)
            if text:
                SubjectComment.objects.update_or_create(
                    school=request.school,
                    learner_id=learner_id,
                    term=term,
                    subject=subject,
                    defaults={"text": text},
                )
            else:
                SubjectComment.objects.filter(learner_id=learner_id, term=term, subject=subject).delete()
            saved += 1
        # Draft report cards show the new comments at once.
        for card in ReportCard.objects.filter(
            school=request.school, term=term, learner_id__in=learner_ids, status=ReportCard.Status.DRAFT
        ).select_related("learner"):
            comments = subject_comments(card.learner, term, card.snapshot.get("subjects", []))
            for row in card.snapshot.get("subjects", []):
                row["comment"] = comments.get(row["subject_id"], row.get("comment", ""))
            card.save(update_fields=["snapshot"])
        return Response({"saved": saved})


class CommentBankViewSet(SchoolViewSet):
    queryset = CommentBank.objects.all()
    serializer_class = s.CommentBankSerializer
    perms = {"read": "reports.view", "write": "assessment.manage"}
    module = MODULE
    platform_setup = True


class UnebResultViewSet(SchoolViewSet):
    queryset = UnebResult.objects.all()
    serializer_class = s.UnebResultSerializer
    perms = {"read": "assessment.view", "write": "assessment.manage"}
    module = MODULE
    filterset_fields = ["year", "level", "division", "learner"]
    search_fields = ["candidate_name", "index_number"]

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser], url_path="import")
    def import_csv(self, request):
        upload = request.FILES.get("file")
        level = request.data.get("level")
        if (
            upload is None
            or level not in UnebResult.Level.values
            or not str(request.data.get("year", "")).isdigit()
        ):
            raise BusinessRuleError(
                {"detail": "Attach a CSV and give the year and level (PLE, UCE or UACE)."}
            )
        return Response(import_results(request.school, int(request.data["year"]), level, upload))

    @action(detail=False, methods=["get"])
    def analysis(self, request):
        level = request.query_params.get("level", "PLE")
        return Response(analyse(request.school, level))


class VerifyReportCardView(APIView):
    """Public page behind the QR code: shows only enough to prove the card is genuine."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        card = (
            ReportCard.objects.filter(verify_token=token)
            .select_related("school", "learner", "term__academic_year")
            .first()
        )
        if card is None or card.status == ReportCard.Status.DRAFT:
            return Response(
                {"valid": False, "detail": "No published report card matches this code."}, status=404
            )
        return Response(
            {
                "valid": card.status == ReportCard.Status.PUBLISHED,
                "status": card.get_status_display(),
                "school": card.school.name,
                "learner": card.learner.full_name,
                "term": str(card.term),
                "serial": card.serial,
                "published_at": card.published_at,
                "note": "This card was replaced by a corrected one."
                if card.status == ReportCard.Status.SUPERSEDED
                else "",
            }
        )
