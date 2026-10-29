"""The 360° learner profile: one call returns the header, every tab the viewer's role may
see, and the key analytics."""

from decimal import Decimal

from apps.assessment.models import ReportCard, ResultSummary
from apps.attendance.models import AttendanceRecord
from apps.attendance.services import CHRONIC_RATE, consecutive_absences, learner_stats
from apps.core.audit import log_access
from apps.core.models import AuditLog
from apps.core.modules import module_enabled
from apps.core.permissions import has_perm
from apps.learners.models import Enrolment, LearnerGuardian, StreamChange
from apps.schoolsetup.models import Term, current_term

DROP_THRESHOLD = 10


def _f(value):
    return float(value) if value is not None else None


def header(learner, term):
    enrolment = (
        learner.enrolments.filter(term=term).select_related("school_class", "stream").first()
        if term
        else None
    )
    result = ResultSummary.objects.filter(learner=learner, term=term).first() if term else None
    stats = learner_stats(learner, term) if term else {"rate": None}
    open_cases = learner.discipline_cases.filter(status="open").count()
    promotion = learner.promotion_decisions.order_by("-created_at").first()
    return {
        "id": learner.id,
        "name": learner.full_name,
        "first_name": learner.first_name,
        "last_name": learner.last_name,
        "adm_no": learner.adm_no,
        "lin": learner.lin,
        "photo": learner.photo.url if learner.photo else None,
        "sex": learner.get_sex_display(),
        "date_of_birth": learner.date_of_birth,
        "class": enrolment.school_class.name if enrolment else None,
        "stream": enrolment.stream.name if enrolment and enrolment.stream else None,
        "house": learner.house.name if learner.house else None,
        "residence": learner.get_residence_display(),
        "status": learner.get_status_display(),
        "indicators": {
            "average": _f(result.average) if result else None,
            "position": result.position if result else None,
            "out_of": result.out_of if result else None,
            "aggregate": result.aggregate if result else None,
            "division": result.division if result else None,
            "attendance_rate": stats["rate"],
            "open_discipline_cases": open_cases,
            "medical_alert": "See nurse" if learner.has_medical_alert else None,
            "promotion_status": promotion.get_final_display() if promotion else None,
        },
    }


def performance_trend(learner):
    rows = (
        ResultSummary.objects.filter(learner=learner)
        .select_related("term__academic_year")
        .order_by("term__start_date")
    )
    return [
        {
            "term_id": r.term_id,
            "term": str(r.term),
            "average": _f(r.average),
            "position": r.position,
            "out_of": r.out_of,
            "aggregate": r.aggregate,
            "division": r.division,
            "points": _f(r.points),
        }
        for r in rows
    ]


def subjects_vs_class(learner, term):
    result = ResultSummary.objects.filter(learner=learner, term=term).first()
    if result is None:
        return []
    classmates = ResultSummary.objects.filter(term=term, school_class=result.school_class).values_list(
        "subjects", flat=True
    )
    totals = {}
    for subjects in classmates:
        for row in subjects:
            if row.get("score") is not None:
                totals.setdefault(row["subject_id"], []).append(row["score"])
    return [
        {
            "subject": r["name"],
            "score": r["score"],
            "grade": r.get("grade"),
            "class_average": round(sum(totals[r["subject_id"]]) / len(totals[r["subject_id"]]), 1)
            if totals.get(r["subject_id"])
            else None,
        }
        for r in result.subjects
    ]


def subject_changes(learner):
    """Term-on-term change per subject; drops of 10 marks or more are flagged."""
    results = list(ResultSummary.objects.filter(learner=learner).order_by("-term__start_date")[:2])
    if len(results) < 2:
        return []
    now, before = results
    previous = {r["subject_id"]: r.get("score") for r in before.subjects}
    changes = []
    for row in now.subjects:
        old = previous.get(row["subject_id"])
        if row.get("score") is None or old is None:
            continue
        change = round(row["score"] - old, 1)
        changes.append(
            {
                "subject": row["name"],
                "previous": old,
                "current": row["score"],
                "change": change,
                "dropped": change <= -DROP_THRESHOLD,
            }
        )
    return changes


def attendance_by_term(learner):
    data = []
    terms = (
        Term.objects.filter(enrolments__learner=learner)
        .distinct()
        .order_by("start_date")
        .select_related("academic_year")
    )
    averages = {r.term_id: _f(r.average) for r in ResultSummary.objects.filter(learner=learner)}
    for term in terms:
        stats = learner_stats(learner, term)
        data.append(
            {
                "term": str(term),
                "rate": stats["rate"],
                "absent": stats["absent"],
                "average": averages.get(term.id),
            }
        )
    return data


def early_warnings(learner, term, trend):
    flags = []
    averages = [t["average"] for t in trend if t["average"] is not None]
    if len(averages) >= 2 and averages[-1] < averages[-2] - 5:
        flags.append(
            {
                "kind": "falling_grades",
                "message": f"Average fell from {averages[-2]:.1f} to {averages[-1]:.1f}.",
            }
        )
    if term:
        rate = learner_stats(learner, term)["rate"]
        streak = consecutive_absences(learner, term)
        if (rate is not None and rate < CHRONIC_RATE) or streak >= 3:
            flags.append(
                {
                    "kind": "chronic_absence",
                    "message": f"Attendance {rate}% this term; {streak} absences in a row.",
                }
            )
    if module_enabled(learner.school, "sickbay"):
        from datetime import timedelta

        from django.utils import timezone

        visits = learner.sickbay_visits.filter(visited_at__gte=timezone.now() - timedelta(days=30)).count()
        if visits >= 3:
            flags.append({"kind": "repeated_sickbay", "message": f"{visits} sickbay visits in 30 days."})
    open_cases = learner.discipline_cases.filter(status="open").count()
    if open_cases:
        flags.append({"kind": "discipline", "message": f"{open_cases} open discipline case(s)."})
    return flags


def projected_promotion(learner, term):
    from apps.promotion.services import decide, measure, rule_for

    enrolment = (
        Enrolment.objects.filter(learner=learner, term=term).select_related("school_class__section").first()
        if term
        else None
    )
    if enrolment is None:
        return None
    if enrolment.school_class.is_candidate_class:
        return {"outcome": "Completes this year"}
    rule = rule_for(enrolment.school_class)
    if rule is None:
        return None
    value = measure(rule, learner, term)
    if value is None and rule.measure == "annual_average":
        values = [
            r.average
            for r in ResultSummary.objects.filter(learner=learner, term__academic_year=term.academic_year)
            if r.average is not None
        ]
        value = sum(values) / len(values) if values else None
    outcome = decide(rule, value)
    return {
        "rule": str(rule),
        "value": _f(Decimal(str(value))) if value is not None else None,
        "outcome": getattr(outcome, "label", outcome),
    }


def build_profile(request, learner):
    school = request.school
    term = current_term(school)
    can = lambda p: has_perm(request, p)  # noqa: E731
    trend = performance_trend(learner) if can("assessment.view") or can("reports.view") else []
    profile = {"header": header(learner, term), "tabs": {}, "analytics": {}}
    tabs = profile["tabs"]

    links = LearnerGuardian.objects.filter(learner=learner).select_related("guardian")
    sibling_ids = (
        LearnerGuardian.objects.filter(guardian__in=[l.guardian for l in links])
        .exclude(learner=learner)
        .values_list("learner_id", flat=True)
    )
    tabs["personal"] = {
        "date_of_birth": learner.date_of_birth,
        "nationality": learner.nationality,
        "religion": learner.religion,
        "address": learner.address,
        "district": learner.district,
        "previous_school": learner.previous_school,
        "admitted_on": learner.admitted_on,
        "special_needs": learner.special_needs,
        "guardians": [
            {
                "id": l.guardian.id,
                "name": l.guardian.full_name,
                "phone": l.guardian.phone,
                "email": l.guardian.email,
                "relationship": l.relationship,
                "is_primary": l.is_primary,
            }
            for l in links
        ],
        "siblings": [
            {"id": s.id, "name": s.full_name, "adm_no": s.adm_no}
            for s in learner.__class__.objects.filter(pk__in=sibling_ids)
        ],
        "documents": [
            {"id": d.id, "title": d.title, "url": d.file.url if d.file else None}
            for d in learner.documents.all()
        ],
    }
    if can("assessment.view") or can("reports.view"):
        tabs["academics"] = {
            "results": trend,
            "current_subjects": subjects_vs_class(learner, term) if term else [],
            "report_cards": [
                {"id": c.id, "term": str(c.term), "serial": c.serial, "status": c.get_status_display()}
                for c in ReportCard.objects.filter(learner=learner)
                .select_related("term__academic_year")
                .order_by("-term__start_date")
            ],
            "subjects_taken": list(
                learner.subject_enrolments.select_related("subject")
                .values_list("subject__name", flat=True)
                .distinct()
            ),
            "combination": learner.combination.code if learner.combination else None,
            "competencies": list(
                learner.aoi_scores.filter(term=term).values(
                    "competency__subject__name", "competency__topic", "score"
                )
            )
            if term
            else [],
        }
    if can("attendance.view"):
        records = (
            AttendanceRecord.objects.filter(
                learner=learner, session__term=term, session__slot__isnull=True
            ).select_related("session")
            if term
            else []
        )
        tabs["attendance"] = {
            "this_term": learner_stats(learner, term) if term else None,
            "calendar": [{"date": r.session.date, "status": r.status, "reason": r.reason} for r in records],
            "by_term": attendance_by_term(learner),
        }
    if can("discipline.view"):
        tabs["discipline"] = {
            "cases": list(
                learner.discipline_cases.values(
                    "id", "date", "category", "severity", "description", "status", "action_taken"
                )
            ),
            "counselling": list(learner.counselling_referrals.values("id", "date", "reason", "status")),
            "achievements": list(learner.achievements.values("id", "date", "title", "category")),
        }
    if can("health.view") and (
        module_enabled(school, "sickbay") or learner.medical_notes or learner.allergies
    ):
        log_access(school, "learner.profile.health", learner.id)
        tabs["health"] = {
            "allergies": learner.allergies,
            "medical_notes": learner.medical_notes,
            "visits": list(
                learner.sickbay_visits.values("id", "visited_at", "complaint", "treatment", "outcome")[:50]
            )
            if module_enabled(school, "sickbay")
            else [],
            "immunisations": list(learner.immunisations.values("vaccine", "dose", "date"))
            if module_enabled(school, "sickbay")
            else [],
        }
    library_on, stores_on = module_enabled(school, "library"), module_enabled(school, "stores")
    if (library_on and can("library.view")) or (stores_on and can("stores.view")):
        tab = {}
        if library_on:
            tab["loans"] = [
                {
                    "title": l.copy.book.title,
                    "issued_on": l.issued_on,
                    "due_on": l.due_on,
                    "returned_on": l.returned_on,
                    "overdue": l.is_overdue,
                }
                for l in learner.loans.select_related("copy__book")[:50]
            ]
        if stores_on and term:
            from apps.stores.models import Requirement

            cleared = {c.requirement_id: c.quantity_brought for c in learner.requirement_clearances.all()}
            enrolment = learner.enrolments.filter(term=term).first()
            reqs = Requirement.objects.filter(school=school, term=term)
            tab["requirements"] = [
                {
                    "name": r.name,
                    "needed": _f(r.quantity_per_learner),
                    "brought": _f(cleared.get(r.id, 0)),
                    "cleared": cleared.get(r.id, 0) >= r.quantity_per_learner,
                }
                for r in reqs
                if enrolment
                and (r.school_class_id in (None, enrolment.school_class_id))
                and (r.section_id in (None, enrolment.school_class.section_id))
            ]
        tabs["library_requirements"] = tab
    history = {
        "enrolments": [
            {"term": str(e.term), "class": e.school_class.name, "stream": e.stream.name if e.stream else None}
            for e in learner.enrolments.select_related(
                "term__academic_year", "school_class", "stream"
            ).order_by("term__start_date")
        ],
        "promotions": [
            {
                "term": str(d.batch.term),
                "decision": d.get_final_display(),
                "overridden": bool(d.override_reason),
                "reason": d.override_reason,
            }
            for d in learner.promotion_decisions.select_related("batch__term__academic_year")
        ],
        "stream_changes": list(
            StreamChange.objects.filter(learner=learner).values(
                "created_at", "from_class__name", "to_class__name", "reason"
            )
        ),
        "exits": list(learner.exits.values("kind", "date", "destination_school", "reason")),
    }
    if can("learners.manage") or can("audit.view"):
        history["audit"] = list(
            AuditLog.objects.filter(
                school=school, entity="learners.learner", object_id=str(learner.id)
            ).values("action", "changes", "timestamp", "user__username")[:100]
        )
    tabs["history"] = history

    profile["analytics"] = {
        "trend": trend,
        "subject_changes": subject_changes(learner) if trend else [],
        "attendance_vs_results": attendance_by_term(learner) if can("attendance.view") else [],
        "early_warnings": early_warnings(learner, term, trend),
        "projected_promotion": projected_promotion(learner, term) if trend else None,
    }
    return profile
