import datetime
from collections import defaultdict

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services import class_scope
from apps.assessment.models import MarkSheet, ResultSummary
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.attendance.services import class_summary
from apps.core.models import AuditLog
from apps.core.modules import module_enabled
from apps.core.permissions import SchoolPermission, has_perm
from apps.core.viewsets import SchoolReadOnlyViewSet
from apps.learners.models import Enrolment, Learner
from apps.schoolsetup.models import CalendarEvent, SchoolClass, Stream, current_term


class DashboardView(APIView):
    """Role dashboard: each block appears only when the user's role and the school's
    modules allow it."""

    permission_classes = [IsAuthenticated, SchoolPermission]

    def get_required_perm(self, request):
        return "dashboard.view"

    def get(self, request):
        school, user = request.school, request.user
        term = current_term(school)
        today = timezone.localdate()
        can = lambda p: has_perm(request, p)  # noqa: E731
        data = {"term": str(term) if term else None, "today": today, "blocks": {}}
        blocks = data["blocks"]

        if can("learners.view"):
            active = Learner.objects.filter(school=school, status=Learner.Status.ACTIVE)
            by_sex = dict(active.values_list("sex").annotate(n=Count("id")))
            enrolled = (
                Enrolment.objects.filter(term=term)
                .values("school_class__name")
                .annotate(n=Count("id"))
                .order_by("school_class__order")
                if term
                else []
            )
            blocks["learners"] = {
                "active": active.count(),
                "male": by_sex.get("M", 0),
                "female": by_sex.get("F", 0),
                "boarding": active.filter(residence="boarding").count(),
                "by_class": [{"class": r["school_class__name"], "learners": r["n"]} for r in enrolled],
            }
        if can("staff.view"):
            from apps.staff.models import LeaveRequest, StaffProfile

            staff = StaffProfile.objects.filter(school=school).exclude(status="left")
            blocks["staff"] = {
                "total": staff.count(),
                "teaching": staff.filter(kind="teaching").count(),
                "on_leave": staff.filter(status="on_leave").count(),
                "pending_leave": LeaveRequest.objects.filter(school=school, status="pending").count(),
            }
        if can("attendance.view") and term:
            sessions = AttendanceSession.objects.filter(school=school, date=today, slot__isnull=True)
            records = AttendanceRecord.objects.filter(session__in=sessions)
            totals = records.aggregate(
                total=Count("id"), present=Count("id", filter=Q(status__in=["present", "late"]))
            )
            scope = class_scope(user, school)
            classes = SchoolClass.objects.filter(school=school)
            if scope is not None:
                classes = classes.filter(pk__in=scope)
            taken = set(sessions.values_list("school_class_id", flat=True))
            blocks["attendance_today"] = {
                "registers_taken": len(taken),
                "present_rate": round(100 * totals["present"] / totals["total"], 1)
                if totals["total"]
                else None,
                "classes_not_taken": [{"id": c.id, "name": c.name} for c in classes if c.id not in taken],
            }
        if can("assessment.view") and term:
            sheets = MarkSheet.objects.filter(school=school, exam__term=term)
            scope = class_scope(user, school)
            if scope is not None:
                sheets = sheets.filter(school_class_id__in=scope)
            counts = dict(sheets.values_list("status").annotate(n=Count("id")))
            blocks["marks"] = {"by_status": counts, "total": sum(counts.values())}
            if can("marks.enter"):
                from apps.curriculum.models import SubjectAllocation

                mine = SubjectAllocation.objects.filter(school=school, teacher__user=user)
                my_sheets = (
                    sheets.filter(status__in=["draft", "returned"]).filter(
                        Q(
                            *[Q(subject_id=a.subject_id, school_class_id=a.school_class_id) for a in mine],
                            _connector=Q.OR,
                        )
                    )
                    if mine
                    else sheets.none()
                )
                blocks["my_mark_sheets"] = [
                    {
                        "id": s.id,
                        "label": str(s),
                        "status": s.get_status_display(),
                        "return_comment": s.return_comment,
                    }
                    for s in my_sheets.select_related("exam", "subject", "paper", "school_class", "stream")[
                        :20
                    ]
                ]
            if can("marks.review") or can("marks.approve"):
                blocks["sheets_awaiting_review"] = sheets.filter(status__in=["submitted", "reviewed"]).count()
        if can("finance.view") and module_enabled(school, "finance"):
            from apps.finance.models import Expense, PettyCashFloat
            from apps.finance.reports import budget_vs_actual

            spent = Expense.objects.filter(school=school, status__in=Expense.SPENT)
            term_total = spent.filter(term=term).aggregate(t=Sum("amount"))["t"] or 0 if term else 0
            learners = Enrolment.objects.filter(term=term).count() if term else 0
            bva = budget_vs_actual(school, term) if term else {"lines": []}
            blocks["finance"] = {
                "today": float(spent.filter(date=today).aggregate(t=Sum("amount"))["t"] or 0),
                "this_week": float(
                    spent.filter(date__gte=today - datetime.timedelta(days=today.weekday())).aggregate(
                        t=Sum("amount")
                    )["t"]
                    or 0
                ),
                "this_term": float(term_total),
                "cost_per_learner": round(float(term_total) / learners) if learners else None,
                "pending_approvals": Expense.objects.filter(school=school, status="pending").count(),
                "budget_alerts": [line for line in bva["lines"] if line["status"] in ("warning", "over")],
                "low_petty_cash": [
                    f.name
                    for f in PettyCashFloat.objects.filter(school=school, is_active=True)
                    if f.balance < f.replenish_below
                ],
                "by_category": [
                    {"category": r["category__name"], "total": float(r["t"])}
                    for r in spent.filter(term=term)
                    .values("category__name")
                    .annotate(t=Sum("amount"))
                    .order_by("-t")[:8]
                ]
                if term
                else [],
            }
        alerts = []
        if module_enabled(school, "library") and can("library.view"):
            from apps.library.models import Loan

            overdue = Loan.objects.filter(school=school, returned_on__isnull=True, due_on__lt=today).count()
            if overdue:
                alerts.append(
                    {
                        "kind": "library",
                        "message": f"{overdue} overdue library book(s)",
                        "link": "/library/loans?overdue=1",
                    }
                )
        if module_enabled(school, "stores") and can("stores.view"):
            from apps.stores.models import Item

            low = [i.name for i in Item.objects.filter(school=school) if i.quantity <= i.reorder_level]
            if low:
                alerts.append(
                    {
                        "kind": "stores",
                        "message": f"{len(low)} item(s) at or below reorder level",
                        "link": "/stores/items",
                    }
                )
        if can("discipline.view"):
            from apps.discipline.models import DisciplineCase

            open_cases = DisciplineCase.objects.filter(school=school, status="open").count()
            if open_cases:
                alerts.append(
                    {
                        "kind": "discipline",
                        "message": f"{open_cases} open discipline case(s)",
                        "link": "/discipline",
                    }
                )
        blocks["alerts"] = alerts
        if can("communication.view"):
            from apps.communication.models import Notification

            blocks["unread_notifications"] = Notification.objects.filter(
                user=user, read_at__isnull=True
            ).count()
        blocks["upcoming_events"] = list(
            CalendarEvent.objects.filter(school=school, start_date__gte=today).values(
                "id", "title", "kind", "start_date"
            )[:5]
        )
        return Response(data)


class AnalyticsView(APIView):
    """School-wide academic analytics: subject and teacher performance, and attendance
    against results, for a term."""

    permission_classes = [IsAuthenticated, SchoolPermission]

    def get_required_perm(self, request):
        return "assessment.view"

    def get(self, request):
        from apps.curriculum.models import SubjectAllocation
        from apps.schoolsetup.models import Term

        school = request.school
        term = Term.objects.filter(
            school=school, pk=request.query_params.get("term")
        ).first() or current_term(school)
        if term is None:
            return Response({"detail": "No term yet."})
        results = ResultSummary.objects.filter(school=school, term=term)
        if request.query_params.get("school_class"):
            results = results.filter(school_class_id=request.query_params["school_class"])
        by_subject = defaultdict(list)
        by_subject_class = defaultdict(list)
        for r in results.select_related("school_class"):
            for row in r.subjects:
                if row.get("score") is not None:
                    by_subject[row["name"]].append(row["score"])
                    by_subject_class[(row["subject_id"], r.school_class_id)].append(row["score"])
        teachers = defaultdict(list)
        for alloc in SubjectAllocation.objects.filter(school=school).select_related(
            "teacher", "subject", "school_class"
        ):
            scores = by_subject_class.get((alloc.subject_id, alloc.school_class_id))
            if scores:
                teachers[alloc.teacher.full_name].append(
                    {
                        "subject": alloc.subject.name,
                        "class": alloc.school_class.name,
                        "average": round(sum(scores) / len(scores), 1),
                        "learners": len(scores),
                    }
                )
        buckets = defaultdict(list)
        for r in results:
            if r.average is None:
                continue
            rate = None
            stats = AttendanceRecord.objects.filter(
                learner_id=r.learner_id, session__term=term, session__slot__isnull=True
            ).aggregate(total=Count("id"), present=Count("id", filter=Q(status__in=["present", "late"])))
            if stats["total"]:
                rate = 100 * stats["present"] / stats["total"]
            band = (
                "no data"
                if rate is None
                else (
                    "95%+"
                    if rate >= 95
                    else "85–94%"
                    if rate >= 85
                    else "70–84%"
                    if rate >= 70
                    else "below 70%"
                )
            )
            buckets[band].append(float(r.average))
        divisions = dict(results.exclude(division="").values_list("division").annotate(n=Count("id")))
        return Response(
            {
                "term": str(term),
                "subjects": sorted(
                    [
                        {"subject": k, "average": round(sum(v) / len(v), 1), "learners": len(v)}
                        for k, v in by_subject.items()
                    ],
                    key=lambda x: -x["average"],
                ),
                "teachers": [{"teacher": k, "classes": v} for k, v in sorted(teachers.items())],
                "attendance_vs_results": [
                    {"attendance": k, "average": round(sum(v) / len(v), 1), "learners": len(v)}
                    for k, v in sorted(buckets.items())
                ],
                "divisions": divisions,
            }
        )


class ChronicAbsenceView(APIView):
    permission_classes = [IsAuthenticated, SchoolPermission]
    module = "attendance"

    def get_required_perm(self, request):
        return "attendance.view"

    def get(self, request):
        term = current_term(request.school)
        if term is None:
            return Response([])
        scope = class_scope(request.user, request.school)
        classes = SchoolClass.objects.filter(school=request.school).order_by("order")
        if request.query_params.get("school_class"):
            classes = classes.filter(pk=request.query_params["school_class"])
        stream = None
        if request.query_params.get("stream"):
            stream = Stream.objects.filter(school=request.school, pk=request.query_params["stream"]).first()
        rows = []
        for school_class in classes:
            if scope is not None and school_class.id not in scope:
                continue
            in_class = stream if stream and stream.school_class_id == school_class.id else None
            if stream and in_class is None:
                continue
            rows += [
                dict(r, **{"class": str(in_class or school_class)})
                for r in class_summary(request.school, term, school_class, in_class)
                if r["chronic"]
            ]
        return Response(rows)


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", default=None, read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "entity",
            "object_id",
            "object_repr",
            "action",
            "changes",
            "user",
            "user_name",
            "timestamp",
        ]


class AuditLogViewSet(SchoolReadOnlyViewSet):
    queryset = AuditLog.objects.select_related("user")
    serializer_class = AuditLogSerializer
    perms = {"read": "audit.view"}
    filterset_fields = {
        "entity": ["exact"],
        "object_id": ["exact"],
        "action": ["exact"],
        "user": ["exact"],
        "timestamp": ["gte", "lte"],
    }
    search_fields = ["object_repr", "entity"]
