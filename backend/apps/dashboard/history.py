"""Performance history: how the school, a class, a subject or one learner did term by term.

Results come from each term's computed results (ResultSummary). A past term whose marks were
approved but whose results were never computed is computed here first, from approved marks
only, so its history is not missing.
"""

from collections import defaultdict
from statistics import mean

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services import class_scope
from apps.assessment.models import MarkSheet, ReportCard, ResultSummary
from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import SchoolPermission
from apps.learners.models import Learner
from apps.schoolsetup.models import SchoolClass, Stream, Term

PASS_MARK = 50


def _r(value, places=1):
    return None if value is None else round(float(value), places)


def fill_missing_results(school, school_class):
    """Compute results for any term where the class has approved marks but no results yet."""
    from apps.assessment.grading import compute_class_results

    with_results = set(
        ResultSummary.objects.filter(school=school, school_class=school_class).values_list(
            "term_id", flat=True
        )
    )
    approved_terms = set(
        MarkSheet.objects.filter(
            school=school, school_class=school_class, status=MarkSheet.Status.APPROVED
        ).values_list("exam__term_id", flat=True)
    )
    for term in Term.objects.filter(pk__in=approved_terms - with_results):
        compute_class_results(term, school_class)


def summarise(results):
    """Headline figures for a set of learners' results in one term."""
    averages = [float(r.average) for r in results if r.average is not None]
    divisions = defaultdict(int)
    for r in results:
        if r.division:
            divisions[r.division] += 1
    return {
        "learners": len(results),
        "average": _r(mean(averages)) if averages else None,
        "highest": _r(max(averages)) if averages else None,
        "lowest": _r(min(averages)) if averages else None,
        "pass_rate": _r(100 * sum(1 for a in averages if a >= PASS_MARK) / len(averages))
        if averages
        else None,
        "divisions": dict(sorted(divisions.items())),
    }


class HistoryView(APIView):
    """Term-by-term results.

    No class: every class's average per term (the school's trend).
    A class (and optional stream): per term, the headline figures, each subject's average
    and each stream's average."""

    permission_classes = [IsAuthenticated, SchoolPermission]
    module = "assessment"

    def get_required_perm(self, request):
        return "assessment.view"

    def get(self, request):
        school = request.school
        scope = class_scope(request.user, school)
        params = request.query_params
        classes = SchoolClass.objects.filter(school=school).order_by("order")
        if scope is not None:
            classes = classes.filter(pk__in=scope)
        results = ResultSummary.objects.filter(school=school).select_related("term__academic_year")

        if not params.get("school_class"):
            for school_class in classes:
                fill_missing_results(school, school_class)
            results = list(results.filter(school_class__in=classes))
            terms = sorted({r.term for r in results}, key=lambda t: t.start_date)
            by = defaultdict(list)
            for r in results:
                by[(r.school_class_id, r.term_id)].append(r)
            school_by_term = {t.id: summarise([r for r in results if r.term_id == t.id]) for t in terms}
            return Response(
                {
                    "terms": [{"id": t.id, "label": str(t)} for t in terms],
                    "school": [{"term": t.id, **school_by_term[t.id]} for t in terms],
                    "classes": [
                        {
                            "id": c.id,
                            "name": c.name,
                            "terms": {t.id: summarise(by[(c.id, t.id)])["average"] for t in terms},
                        }
                        for c in classes
                        if any(by[(c.id, t.id)] for t in terms)
                    ],
                }
            )

        school_class = classes.filter(pk=params["school_class"]).first()
        if school_class is None:
            raise BusinessRuleError({"school_class": "Choose one of your classes."})
        fill_missing_results(school, school_class)
        results = results.filter(school_class=school_class)
        stream = None
        if params.get("stream"):
            stream = Stream.objects.filter(
                school=school, pk=params["stream"], school_class=school_class
            ).first()
            results = results.filter(stream=stream)
        results = list(results)
        terms = sorted({r.term for r in results}, key=lambda t: t.start_date)
        rows = []
        for term in terms:
            in_term = [r for r in results if r.term_id == term.id]
            subjects = defaultdict(list)
            for r in in_term:
                for row in r.subjects:
                    if row.get("score") is not None:
                        subjects[row["name"]].append(float(row["score"]))
            streams = defaultdict(list)
            for r in in_term:
                if r.stream_id and r.average is not None:
                    streams[r.stream_id].append(float(r.average))
            rows.append(
                {
                    "term": term.id,
                    "label": str(term),
                    **summarise(in_term),
                    "subjects": {name: _r(mean(v)) for name, v in sorted(subjects.items())},
                    "streams": {
                        s.name: _r(mean(streams[s.id]))
                        for s in school_class.streams.all()
                        if streams.get(s.id)
                    },
                }
            )
        return Response(
            {
                "class": str(stream or school_class),
                "terms": rows,
                "subjects": sorted({name for row in rows for name in row["subjects"]}),
            }
        )


class LearnerHistoryView(APIView):
    """One learner's results in every term, with the report card issued for each."""

    permission_classes = [IsAuthenticated, SchoolPermission]
    module = "assessment"

    def get_required_perm(self, request):
        return "assessment.view"

    def get(self, request, pk):
        school = request.school
        learner = Learner.objects.filter(school=school, pk=pk).first()
        if learner is None:
            raise BusinessRuleError({"detail": "Unknown learner."})
        scope = class_scope(request.user, school)
        for school_class in SchoolClass.objects.filter(enrolments__learner=learner).distinct():
            fill_missing_results(school, school_class)
        results = list(
            ResultSummary.objects.filter(learner=learner)
            .select_related("term__academic_year", "school_class", "stream")
            .order_by("term__start_date")
        )
        if scope is not None and not any(r.school_class_id in scope for r in results):
            raise BusinessRuleError({"detail": "This learner is not in one of your classes."})
        cards = {
            c.term_id: c
            for c in ReportCard.objects.filter(learner=learner)
            .exclude(status=ReportCard.Status.SUPERSEDED)
            .order_by("created_at")
        }
        return Response(
            {
                "learner": {"id": learner.id, "name": learner.full_name, "adm_no": learner.adm_no},
                "terms": [
                    {
                        "term": r.term_id,
                        "label": str(r.term),
                        "class": str(r.stream or r.school_class),
                        "average": _r(r.average),
                        "total": _r(r.total),
                        "aggregate": r.aggregate,
                        "division": r.division,
                        "points": _r(r.points),
                        "position": r.position,
                        "out_of": r.out_of,
                        "complete": r.is_complete,
                        "subjects": {row["name"]: row.get("score") for row in r.subjects},
                        "grades": {row["name"]: row.get("grade") for row in r.subjects},
                        "report_card": (
                            {"id": cards[r.term_id].id, "status": cards[r.term_id].status}
                            if r.term_id in cards
                            else None
                        ),
                    }
                    for r in results
                ],
            }
        )
