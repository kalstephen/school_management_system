"""Apply offline changes (roll call and marks) with idempotency and conflict detection.

Rules:
  * the same op_id is applied once; resending returns the first result
  * if the record changed on the server since the phone last saw it (version differs)
    and the values differ, the change is held as a conflict for the teacher to resolve,
    never silently overwritten
  * changes to locked mark sheets are rejected
"""

import datetime
import uuid

from django.db import transaction

from apps.accounts.services import can_enter_marks, class_scope
from apps.assessment.models import Mark, MarkSheet
from apps.assessment.services import parse_score, sheet_learners
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.learners.services import learners_in
from apps.schoolsetup.models import SchoolClass, Stream, current_term, term_for_date

from .models import SyncOp


class Reject(Exception):
    pass


def _attendance(school, user, payload, base_version, force=False):
    school_class = SchoolClass.objects.filter(school=school, pk=payload.get("school_class")).first()
    if school_class is None:
        raise Reject("Unknown class.")
    scope = class_scope(user, school)
    if scope is not None and school_class.id not in scope:
        raise Reject("You are not assigned to this class.")
    stream = (
        Stream.objects.filter(school=school, pk=payload.get("stream")).first()
        if payload.get("stream")
        else None
    )
    date = datetime.date.fromisoformat(payload["date"])
    term = term_for_date(school, date) or current_term(school)
    if term is None:
        raise Reject("No term is set up.")
    if not learners_in(school, term, school_class, stream).filter(pk=payload.get("learner")).exists():
        raise Reject("The learner is not in this class.")
    session, _ = AttendanceSession.objects.get_or_create(
        school=school,
        school_class=school_class,
        stream=stream,
        date=date,
        slot_id=payload.get("slot"),
        defaults={"term": term, "taken_by": user},
    )
    record = AttendanceRecord.objects.filter(session=session, learner_id=payload["learner"]).first()
    status, reason = payload.get("status", "present"), payload.get("reason", "")
    if record is None:
        record = AttendanceRecord.objects.create(
            school=school, session=session, learner_id=payload["learner"], status=status, reason=reason
        )
        return "applied", "", record.version, None
    if record.status == status and record.reason == reason:
        return "applied", "No change", record.version, None
    if record.version != base_version and not force:
        return (
            "conflict",
            "Someone else changed this since you went offline.",
            record.version,
            {"status": record.status, "reason": record.reason},
        )
    record.status, record.reason = status, reason
    record.save()
    return "applied", "", record.version, None


def _mark(school, user, payload, base_version, force=False):
    sheet = (
        MarkSheet.objects.filter(school=school, pk=payload.get("mark_sheet")).select_related("exam").first()
    )
    if sheet is None:
        raise Reject("Unknown mark sheet.")
    if not sheet.is_editable:
        raise Reject(f"The mark sheet is {sheet.get_status_display().lower()}; changes are not allowed.")
    if not can_enter_marks(user, school, sheet.subject_id, sheet.school_class_id):
        raise Reject("You are not allocated to this subject and class.")
    if not sheet_learners(sheet).filter(pk=payload.get("learner")).exists():
        raise Reject("The learner does not take this subject.")
    try:
        score = parse_score(payload.get("score"), sheet.exam.max_mark)
    except ValueError as exc:
        raise Reject(str(exc))
    is_absent = bool(payload.get("is_absent")) and score is None
    mark = Mark.objects.filter(mark_sheet=sheet, learner_id=payload["learner"]).first()
    if mark is None:
        mark = Mark.objects.create(
            school=school, mark_sheet=sheet, learner_id=payload["learner"], score=score, is_absent=is_absent
        )
        return "applied", "", mark.version, None
    if mark.score == score and mark.is_absent == is_absent:
        return "applied", "No change", mark.version, None
    if mark.version != base_version and not force:
        return (
            "conflict",
            "This mark was changed since you went offline.",
            mark.version,
            {"score": str(mark.score) if mark.score is not None else None, "is_absent": mark.is_absent},
        )
    mark.score, mark.is_absent = score, is_absent
    mark.save()
    return "applied", "", mark.version, None


HANDLERS = {"attendance": _attendance, "mark": _mark}


def apply_ops(school, user, ops):
    results = []
    for op in ops:
        try:
            op_id = str(uuid.UUID(str(op.get("op_id"))))
        except ValueError:
            results.append(
                {"op_id": op.get("op_id"), "status": "rejected", "detail": "op_id must be a UUID."}
            )
            continue
        existing = SyncOp.objects.filter(op_id=op_id).first()
        if existing is not None:
            results.append(
                {
                    "op_id": op_id,
                    "status": existing.status,
                    "detail": existing.detail,
                    "duplicate": True,
                    "server_value": existing.server_value,
                }
            )
            continue
        handler = HANDLERS.get(op.get("kind"))
        version, server_value = None, None
        try:
            if handler is None or not op_id:
                raise Reject("Unknown kind of change.")
            with transaction.atomic():
                status, detail, version, server_value = handler(
                    school, user, op.get("payload") or {}, int(op.get("base_version") or 0)
                )
        except (Reject, KeyError, ValueError) as exc:
            status, detail = "rejected", str(exc) or "Invalid change."
        if op_id:
            SyncOp.objects.create(
                op_id=op_id,
                school=school,
                user=user,
                kind=op.get("kind", "")[:20],
                payload=op.get("payload") or {},
                base_version=int(op.get("base_version") or 0),
                status=status,
                detail=detail[:300],
                server_value=server_value,
            )
        results.append(
            {
                "op_id": op_id,
                "status": status,
                "detail": detail,
                "version": version,
                "server_value": server_value,
            }
        )
    return results


def resolve(op, keep):
    """keep='mine' re-applies the phone's value over the server's; keep='server' drops it."""
    if op.status != SyncOp.Status.CONFLICT:
        raise Reject("Only conflicts can be resolved.")
    if keep == "mine":
        with transaction.atomic():
            HANDLERS[op.kind](op.school, op.user, op.payload, 0, force=True)
    op.status = SyncOp.Status.RESOLVED
    op.detail = f"Resolved: kept {'your' if keep == 'mine' else 'the server'} value"
    op.save()
    return op
