"""Grading engines. Each section of the school picks one rule set:

  generic  – marks, grades and an average (e.g. lower primary P1–P3)
  ple      – PLE-style: grades D1–F9 with points 1–9, aggregate of the 4 aggregate
             subjects, division I–IV or U
  cbc      – lower-secondary competency-based curriculum: school-based assessment from
             activities of integration (scores 1–3) plus the exam, achievement level A–E
  uace     – A-Level: principal grades A–F with points, subsidiaries 1 point on a pass
  nursery  – descriptive ratings, nothing numeric

Grade bands come from the section's grading scale, so schools can match their own
or UNEB's current bands without code changes.
"""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from apps.curriculum.models import Subject
from apps.learners.models import Enrolment, SubjectEnrolment
from apps.learners.services import learners_in

from .models import AOIScore, Exam, Mark, MarkSheet, NurseryRating, ResultSummary

PLE_DIVISIONS = [(4, 12, "I"), (13, 23, "II"), (24, 29, "III"), (30, 34, "IV"), (35, 36, "U")]
PLE_AGGREGATE_SUBJECTS = 4
CBC_SCHOOL_BASED_SHARE = Decimal("20")  # % of the subject score from activities of integration
AOI_MAX = Decimal("3")
SUBSIDIARY_PASS_MARK = Decimal("50")


def _r(value, places=1):
    return None if value is None else round(float(value), places)


def ple_division(aggregate):
    if aggregate is None:
        return ""
    for low, high, label in PLE_DIVISIONS:
        if low <= aggregate <= high:
            return label
    return "U"


def subjects_offered(school_class):
    section_level = school_class.section.level
    subjects = Subject.objects.filter(
        school=school_class.school, level=section_level, status=Subject.Status.APPROVED
    ).prefetch_related("classes")
    return [s for s in subjects if not s.classes.all() or school_class in s.classes.all()]


def subjects_taken(learner, offered, chosen_ids):
    """Compulsory subjects for everyone; electives, principals and subsidiaries only when chosen."""
    return [s for s in offered if s.category == Subject.Category.CORE or s.id in chosen_ids]


def term_subject_scores(term, school_class, learner_ids, approved_only=True):
    """Weighted term score per learner and subject, as a percentage.

    A subject's exam score is the mean of its papers; the term score weights the exams
    the learner sat (weights renormalised if one was missed)."""
    exams = {e.id: e for e in Exam.objects.filter(term=term, classes=school_class)}
    sheets = MarkSheet.objects.filter(exam_id__in=exams, school_class=school_class)
    if approved_only:
        sheets = sheets.filter(status=MarkSheet.Status.APPROVED)
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    marks = Mark.objects.filter(
        mark_sheet__in=sheets, learner_id__in=learner_ids, score__isnull=False
    ).values("learner_id", "score", "mark_sheet__subject_id", "mark_sheet__exam_id")
    for m in marks:
        exam = exams[m["mark_sheet__exam_id"]]
        raw[m["learner_id"]][m["mark_sheet__subject_id"]][exam.id].append(m["score"] / exam.max_mark * 100)
    results = defaultdict(dict)
    for learner_id, subjects in raw.items():
        for subject_id, by_exam in subjects.items():
            exam_scores = {eid: sum(v) / len(v) for eid, v in by_exam.items()}
            total_weight = sum(exams[eid].weight for eid in exam_scores)
            score = (
                sum(exams[eid].weight * s for eid, s in exam_scores.items()) / total_weight
                if total_weight
                else None
            )
            results[learner_id][subject_id] = {
                "score": score,
                "exams": {str(eid): _r(s) for eid, s in exam_scores.items()},
            }
    return results, list(exams.values())


def _rank(items, key, field):
    """Competition ranking (1, 2, 2, 4). items: list of (result, sort_key); None keys rank last."""
    ranked = sorted([i for i in items if key(i) is not None], key=key)
    position, previous = 0, object()
    for index, item in enumerate(ranked, start=1):
        k = key(item)
        if k != previous:
            position, previous = index, k
        setattr(item, field, position)
    for item in items:
        if key(item) is None:
            setattr(item, field, None)


def compute_class_results(term, school_class, approved_only=True):
    """Compute and save ResultSummary rows for every learner in a class for a term."""
    school = school_class.school
    section = school_class.section
    rule = section.grading_rule_set
    scale = section.grading_scale
    learners = list(learners_in(school, term, school_class))
    learner_ids = [l.id for l in learners]
    enrolments = {e.learner_id: e for e in Enrolment.objects.filter(term=term, learner_id__in=learner_ids)}
    offered = subjects_offered(school_class)
    chosen = defaultdict(set)
    for row in SubjectEnrolment.objects.filter(
        learner_id__in=learner_ids, academic_year=term.academic_year
    ).values("learner_id", "subject_id"):
        chosen[row["learner_id"]].add(row["subject_id"])
    scores, _ = term_subject_scores(term, school_class, learner_ids, approved_only)
    aoi = defaultdict(list)
    if rule == "cbc":
        for row in AOIScore.objects.filter(term=term, learner_id__in=learner_ids).values(
            "learner_id", "competency__subject_id", "score"
        ):
            aoi[(row["learner_id"], row["competency__subject_id"])].append(row["score"])
    ratings = defaultdict(dict)
    if rule == "nursery":
        for r in NurseryRating.objects.filter(term=term, learner_id__in=learner_ids):
            ratings[r.learner_id][r.learning_area_id] = (r.get_rating_display(), r.remark)

    summaries = []
    with transaction.atomic():
        for learner in learners:
            taken = subjects_taken(learner, offered, chosen[learner.id])
            rows = []
            for subject in taken:
                entry = scores.get(learner.id, {}).get(subject.id, {})
                score = entry.get("score")
                row = {
                    "subject_id": subject.id,
                    "name": subject.name,
                    "short_name": subject.short_name,
                    "category": subject.category,
                    "in_aggregate": subject.in_aggregate,
                    "exams": entry.get("exams", {}),
                    "score": None,
                    "grade": "",
                    "points": None,
                    "descriptor": "",
                }
                if rule == "nursery":
                    rating = ratings[learner.id].get(subject.id)
                    row["grade"], row["descriptor"] = rating if rating else ("", "")
                    rows.append(row)
                    continue
                if rule == "cbc" and score is not None:
                    aoi_scores = aoi.get((learner.id, subject.id))
                    if aoi_scores:
                        aoi_avg = sum(aoi_scores) / len(aoi_scores)
                        row["aoi_average"] = _r(aoi_avg, 2)
                        score = (
                            aoi_avg / AOI_MAX * CBC_SCHOOL_BASED_SHARE
                            + score * (100 - CBC_SCHOOL_BASED_SHARE) / 100
                        )
                row["score"] = _r(score)
                if rule == "uace" and subject.category == Subject.Category.SUBSIDIARY:
                    if score is not None:
                        passed = score >= SUBSIDIARY_PASS_MARK
                        row["grade"], row["points"] = ("Pass", 1.0) if passed else ("Fail", 0.0)
                elif scale is not None and score is not None:
                    band = scale.band_for(Decimal(str(round(score, 2))))
                    if band:
                        row["grade"], row["points"], row["descriptor"] = (
                            band.label,
                            float(band.points),
                            band.descriptor,
                        )
                rows.append(row)

            numeric = [r["score"] for r in rows if r["score"] is not None]
            complete = rule == "nursery" or (len(numeric) == len(rows) and bool(rows))
            total = sum(numeric) if numeric else None
            average = total / len(numeric) if numeric else None
            aggregate = division = points = None
            if rule == "ple":
                agg_rows = [r for r in rows if r["in_aggregate"]]
                if len(agg_rows) == PLE_AGGREGATE_SUBJECTS and all(r["points"] is not None for r in agg_rows):
                    aggregate = int(sum(r["points"] for r in agg_rows))
                    division = ple_division(aggregate)
                else:
                    complete = False
            elif rule == "uace":
                points = sum(r["points"] for r in rows if r["points"] is not None)
            enrolment = enrolments.get(learner.id)
            summary, _ = ResultSummary.objects.update_or_create(
                school=school,
                learner=learner,
                term=term,
                defaults={
                    "school_class": school_class,
                    "stream": enrolment.stream if enrolment else None,
                    "rule_set": rule,
                    "subjects": rows,
                    "total": _r(total, 2),
                    "average": _r(average, 2),
                    "aggregate": aggregate,
                    "division": division or "",
                    "points": points,
                    "is_complete": complete,
                    "out_of": len(learners),
                },
            )
            summaries.append(summary)

        if rule == "ple":
            key = lambda s: None if s.aggregate is None else (s.aggregate, -(s.total or 0))  # noqa: E731
        elif rule == "uace":
            key = lambda s: None if s.points is None else (-s.points, -(s.average or 0))  # noqa: E731
        elif rule == "nursery":
            key = lambda s: None  # noqa: E731
        else:
            key = lambda s: None if s.average is None else -s.average  # noqa: E731
        _rank(summaries, key, "position")
        by_stream = defaultdict(list)
        for s in summaries:
            by_stream[s.stream_id].append(s)
        for group in by_stream.values():
            _rank(group, key, "stream_position")
            for s in group:
                s.out_of = len(summaries)
        for s in summaries:
            ResultSummary.objects.filter(pk=s.pk).update(
                position=s.position, stream_position=s.stream_position, out_of=s.out_of
            )
    return summaries


def unapproved_sheets(term, school_class):
    return MarkSheet.objects.filter(exam__term=term, school_class=school_class).exclude(
        status=MarkSheet.Status.APPROVED
    )
