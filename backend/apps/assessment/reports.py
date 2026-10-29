"""Report cards: build them from computed results, publish them, and reissue them
under a new serial when locked results change."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.attendance.services import learner_stats
from apps.core.exceptions import BusinessRuleError
from apps.curriculum.models import SubjectAllocation

from .grading import compute_class_results, unapproved_sheets
from .models import CommentBank, ReportCard


def verify_url(card):
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/verify/{card.verify_token}"


def _initials(name):
    return "".join(part[0] for part in name.split() if part).upper()


def _teacher_initials(school_class, stream):
    """Initials of the teacher of each subject: the allocated teacher (a stream's own teacher
    first), else the class teacher, who takes every subject not allocated to someone else."""
    initials = {}
    allocations = SubjectAllocation.objects.filter(school_class=school_class).select_related("teacher")
    for alloc in sorted(allocations, key=lambda a: a.stream_id is None):
        if alloc.stream_id in (None, getattr(stream, "id", None)):
            initials.setdefault(alloc.subject_id, _initials(alloc.teacher.full_name))
    lead = (stream.class_teacher if stream else None) or school_class.class_teacher
    return initials, (_initials(lead.full_name) if lead else "")


def subject_comment_presets(school):
    """Subject presets: those for one subject first, then those for any subject."""
    rows = list(CommentBank.objects.filter(school=school, role=CommentBank.Role.SUBJECT))
    return sorted(rows, key=lambda r: r.subject_id is None)


def suggested_subject_comment(presets, subject_id, score):
    if score is None:
        return ""
    for row in presets:
        if row.subject_id in (None, subject_id) and row.min_average <= Decimal(str(score)) <= row.max_average:
            return row.text
    return ""


def subject_comments(learner, term, subjects):
    """{subject_id: comment}: what the teacher wrote, else the preset for the mark."""
    from .models import SubjectComment

    written = dict(
        SubjectComment.objects.filter(learner=learner, term=term).values_list("subject_id", "text")
    )
    presets = subject_comment_presets(learner.school)
    return {
        row["subject_id"]: written.get(row["subject_id"])
        or suggested_subject_comment(presets, row["subject_id"], row.get("score"))
        for row in subjects
    }


def _suggested_comment(school, role, average):
    if average is None:
        return ""
    row = CommentBank.objects.filter(
        school=school, role=role, min_average__lte=average, max_average__gte=average
    ).first()
    return row.text if row else ""


def build_snapshot(result, card=None):
    learner, term, school = result.learner, result.term, result.school
    section = result.school_class.section
    initials, lead = _teacher_initials(result.school_class, result.stream)
    comments = subject_comments(learner, term, result.subjects)
    subjects = [
        dict(row, initials=initials.get(row["subject_id"], lead), comment=comments.get(row["subject_id"], ""))
        for row in result.subjects
    ]
    from .models import Exam

    exams = [
        {
            "id": e.id,
            "name": e.get_kind_display() if e.kind != "other" else e.name,
            "short": e.kind.upper(),
            "weight": float(e.weight),
        }
        for e in Exam.objects.filter(term=term, classes=result.school_class)
    ]
    return {
        "school": {
            "name": school.name,
            "motto": school.motto,
            "address": school.address,
            "phone": school.phone,
            "email": school.email,
            "logo": school.logo.path if school.logo else None,
            "footer": school.report_card_footer,
            "registration_number": school.registration_number,
            "box": school.location,
        },
        "learner": {
            "name": learner.full_name,
            "adm_no": learner.adm_no,
            "lin": learner.lin,
            "sex": learner.get_sex_display(),
            "house": learner.house.name if learner.house else "",
            "photo": learner.photo.path if learner.photo else None,
        },
        "class": result.school_class.name,
        "stream": result.stream.name if result.stream else "",
        "term": str(term),
        "next_term_begins": f"{term.next_term_begins:%A %d %B %Y}" if term.next_term_begins else "",
        "rule_set": result.rule_set,
        "show_positions": section.show_positions,
        "exams": exams,
        "subjects": subjects,
        "total": float(result.total) if result.total is not None else None,
        "average": float(result.average) if result.average is not None else None,
        "aggregate": result.aggregate,
        "division": result.division,
        "points": float(result.points) if result.points is not None else None,
        "position": result.position,
        "stream_position": result.stream_position,
        "out_of": result.out_of,
        "is_complete": result.is_complete,
        "attendance": learner_stats(learner, term),
        "class_teacher_comment": card.class_teacher_comment if card else "",
        "head_comment": card.head_comment if card else "",
        "promotion_note": card.promotion_note if card else "",
    }


def _next_serial(school, term):
    count = ReportCard.objects.filter(school=school, term=term).count() + 1
    while True:
        serial = f"RC{term.academic_year.name}T{term.number}-{school.id:03d}-{count:05d}"
        if not ReportCard.objects.filter(serial=serial).exists():
            return serial
        count += 1


def generate_report_cards(term, school_class, allow_unapproved=False):
    """Compute results and create or refresh draft report cards for a class.

    A published card whose results changed (marks reopened and re-approved) gets a new
    draft card with a new serial; the old one is superseded when the new one is published."""
    pending = unapproved_sheets(term, school_class)
    if pending.exists() and not allow_unapproved:
        raise BusinessRuleError(
            {
                "detail": "Some mark sheets are not approved yet.",
                "pending": [str(sheet) for sheet in pending[:50]],
            }
        )
    school = school_class.school
    results = compute_class_results(term, school_class, approved_only=not allow_unapproved)
    cards = []
    with transaction.atomic():
        for result in results:
            current = (
                ReportCard.objects.filter(learner=result.learner, term=term)
                .exclude(status=ReportCard.Status.SUPERSEDED)
                .order_by("-created_at")
                .first()
            )
            if current is not None and current.status == ReportCard.Status.DRAFT:
                snapshot = build_snapshot(result, current)
                current.result, current.snapshot = result, snapshot
                current.save()
                cards.append(current)
                continue
            snapshot = build_snapshot(result, current)
            if current is not None and _results_part(current.snapshot) == _results_part(snapshot):
                cards.append(current)
                continue
            card = ReportCard(
                school=school,
                learner=result.learner,
                term=term,
                result=result,
                serial=_next_serial(school, term),
                class_teacher_comment=(current.class_teacher_comment if current else "")
                or _suggested_comment(school, "class_teacher", result.average),
                head_comment=(current.head_comment if current else "")
                or _suggested_comment(school, "head", result.average),
                promotion_note=current.promotion_note if current else "",
            )
            card.snapshot = build_snapshot(result, card)
            card.save()
            cards.append(card)
    return cards


RESULT_KEYS = ("subjects", "total", "average", "aggregate", "division", "points", "position")


def _results_part(snapshot):
    return {k: snapshot.get(k) for k in RESULT_KEYS}


def publish(cards, user):
    """Approve and publish drafts. Older published cards for the same learner and term are superseded."""
    published = 0
    with transaction.atomic():
        for card in cards:
            if card.status != ReportCard.Status.DRAFT:
                continue
            card.snapshot["class_teacher_comment"] = card.class_teacher_comment
            card.snapshot["head_comment"] = card.head_comment
            card.snapshot["promotion_note"] = card.promotion_note
            card.status = ReportCard.Status.PUBLISHED
            card.published_at = timezone.now()
            card.approved_by = user
            card.save()
            ReportCard.objects.filter(
                learner=card.learner, term=card.term, status=ReportCard.Status.PUBLISHED
            ).exclude(pk=card.pk).update(status=ReportCard.Status.SUPERSEDED, superseded_by=card)
            published += 1
    return published
