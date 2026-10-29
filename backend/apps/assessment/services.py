"""Mark sheets: who must sit each paper, entering marks with checks, and the approval
workflow (teacher → head of department → DOS → locked)."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessRuleError
from apps.curriculum.models import Subject
from apps.learners.models import SubjectEnrolment
from apps.learners.services import learners_in

from .grading import subjects_offered
from .models import Exam, Mark, MarkSheet

S = MarkSheet.Status


def sheet_learners(sheet):
    """Learners who should have a mark on this sheet: everyone in the class/stream for a
    compulsory subject, otherwise only those who chose the subject."""
    learners = learners_in(sheet.school, sheet.exam.term, sheet.school_class, sheet.stream)
    if sheet.subject.category != Subject.Category.CORE:
        chosen = SubjectEnrolment.objects.filter(
            subject=sheet.subject, academic_year=sheet.exam.term.academic_year
        ).values("learner_id")
        learners = learners.filter(pk__in=chosen)
    return learners.order_by("first_name", "last_name")


def prepare_sheets(exam, school_class, by_stream=False):
    """Create the mark sheets an exam needs for a class: one per subject (or per paper
    when the subject has papers), optionally one per stream."""
    created = 0
    streams = list(school_class.streams.all()) if by_stream else [None]
    for subject in subjects_offered(school_class):
        papers = list(subject.papers.all()) or [None]
        for paper in papers:
            for stream in streams:
                _, made = MarkSheet.objects.get_or_create(
                    school=exam.school,
                    exam=exam,
                    subject=subject,
                    paper=paper,
                    school_class=school_class,
                    stream=stream,
                )
                created += int(made)
    return created


def parse_score(value, max_mark):
    if value in (None, ""):
        return None
    try:
        score = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"'{value}' is not a number")
    if score < 0 or score > max_mark:
        raise ValueError(f"{score} is out of range (0–{max_mark})")
    return score


def save_marks(sheet, entries):
    """entries = [{"learner": id, "score": 67, "is_absent": false}]. Saves valid rows and
    reports each invalid one; nothing is saved on a locked sheet."""
    if not sheet.is_editable:
        raise BusinessRuleError(
            {"detail": f"This mark sheet is {sheet.get_status_display().lower()} and cannot be edited."}
        )
    allowed = set(sheet_learners(sheet).values_list("id", flat=True))
    max_mark = sheet.exam.max_mark
    saved, errors = 0, []
    with transaction.atomic():
        for entry in entries:
            learner_id = int(entry.get("learner"))
            if learner_id not in allowed:
                errors.append(
                    {"learner": learner_id, "error": "This learner does not take this subject in this class."}
                )
                continue
            try:
                score = parse_score(entry.get("score"), max_mark)
            except ValueError as exc:
                errors.append({"learner": learner_id, "error": str(exc)})
                continue
            is_absent = bool(entry.get("is_absent")) and score is None
            mark = Mark.objects.filter(mark_sheet=sheet, learner_id=learner_id).first()
            if mark is None:
                Mark.objects.create(
                    school=sheet.school,
                    mark_sheet=sheet,
                    learner_id=learner_id,
                    score=score,
                    is_absent=is_absent,
                )
            elif mark.score != score or mark.is_absent != is_absent:
                mark.score, mark.is_absent = score, is_absent
                mark.save()
            saved += 1
    return {"saved": saved, "errors": errors}


def missing_marks(sheet):
    have = set(
        Mark.objects.filter(mark_sheet=sheet)
        .exclude(score__isnull=True, is_absent=False)
        .values_list("learner_id", flat=True)
    )
    return [{"learner": l.id, "name": l.full_name} for l in sheet_learners(sheet) if l.id not in have]


def submit(sheet, user):
    if sheet.status not in (S.DRAFT, S.RETURNED):
        raise BusinessRuleError({"detail": "Only draft or returned sheets can be submitted."})
    missing = missing_marks(sheet)
    if missing:
        raise BusinessRuleError(
            {"detail": "Some learners have no mark. Enter a score or mark them absent.", "missing": missing}
        )
    sheet.status, sheet.submitted_by, sheet.submitted_at = S.SUBMITTED, user, timezone.now()
    sheet.return_comment = ""
    sheet.save()
    return sheet


def review(sheet, user):
    if sheet.status != S.SUBMITTED:
        raise BusinessRuleError({"detail": "Only submitted sheets can be reviewed."})
    sheet.status, sheet.reviewed_by, sheet.reviewed_at = S.REVIEWED, user, timezone.now()
    sheet.save()
    return sheet


def approve(sheet, user):
    if sheet.status not in (S.SUBMITTED, S.REVIEWED):
        raise BusinessRuleError({"detail": "Only submitted or reviewed sheets can be approved."})
    sheet.status, sheet.approved_by, sheet.locked_at = S.APPROVED, user, timezone.now()
    sheet.save()
    return sheet


def return_sheet(sheet, user, comment):
    if sheet.status not in (S.SUBMITTED, S.REVIEWED):
        raise BusinessRuleError({"detail": "Only submitted or reviewed sheets can be returned."})
    if not comment:
        raise BusinessRuleError({"comment": "Say what needs correcting."})
    sheet.status, sheet.return_comment = S.RETURNED, comment
    sheet.save()
    return sheet


def reopen(sheet, user, reason):
    """Unlock an approved sheet. Published report cards built on it are reissued under a
    new serial when results are regenerated."""
    if sheet.status != S.APPROVED:
        raise BusinessRuleError({"detail": "Only approved sheets can be reopened."})
    if not reason:
        raise BusinessRuleError({"reason": "A reason is required to reopen approved marks."})
    sheet.status, sheet.reopened_by, sheet.reopen_reason, sheet.locked_at = S.RETURNED, user, reason, None
    sheet.save()
    return sheet


def exams_for_class(term, school_class):
    return Exam.objects.filter(term=term, classes=school_class)
