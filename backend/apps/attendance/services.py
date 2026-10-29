from django.db import transaction
from django.db.models import Count, Q

from apps.learners.services import learners_in

from .models import AttendanceRecord, AttendanceSession

PRESENT_STATUSES = ("present", "late")
CHRONIC_RATE = 80.0  # below this attendance rate (%) a learner is flagged
CONSECUTIVE_ABSENCES = 3


def save_roll_call(school, user, term, date, school_class, stream, records, slot=None):
    """Create or update a register. records = [{"learner": id, "status": "...", "reason": ""}]."""
    allowed = set(learners_in(school, term, school_class, stream).values_list("id", flat=True))
    with transaction.atomic():
        session, _ = AttendanceSession.objects.get_or_create(
            school=school,
            date=date,
            school_class=school_class,
            stream=stream,
            slot=slot,
            defaults={"term": term, "taken_by": user},
        )
        saved = 0
        for item in records:
            learner_id = int(item["learner"])
            if learner_id not in allowed:
                continue
            record, created = AttendanceRecord.objects.get_or_create(
                school=school,
                session=session,
                learner_id=learner_id,
                defaults={"status": item.get("status", "present"), "reason": item.get("reason", "")},
            )
            if not created and (
                record.status != item.get("status") or record.reason != item.get("reason", "")
            ):
                record.status = item.get("status", record.status)
                record.reason = item.get("reason", "")
                record.save()
            saved += 1
    return session, saved


def learner_stats(learner, term):
    """Daily-register attendance for one learner in a term."""
    rows = AttendanceRecord.objects.filter(learner=learner, session__term=term, session__slot__isnull=True)
    totals = rows.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status__in=PRESENT_STATUSES)),
        absent=Count("id", filter=Q(status="absent")),
        late=Count("id", filter=Q(status="late")),
    )
    totals["rate"] = round(100 * totals["present"] / totals["total"], 1) if totals["total"] else None
    return totals


def class_summary(school, term, school_class=None, stream=None):
    """Attendance rate per learner with chronic-absence flags."""
    learners = learners_in(school, term, school_class, stream)
    rows = (
        AttendanceRecord.objects.filter(
            school=school, session__term=term, session__slot__isnull=True, learner__in=learners
        )
        .values("learner_id")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status__in=PRESENT_STATUSES)),
            absent=Count("id", filter=Q(status="absent")),
        )
    )
    by_learner = {r["learner_id"]: r for r in rows}
    result = []
    for learner in learners.order_by("first_name"):
        r = by_learner.get(learner.id, {"total": 0, "present": 0, "absent": 0})
        rate = round(100 * r["present"] / r["total"], 1) if r["total"] else None
        streak = consecutive_absences(learner, term)
        result.append(
            {
                "learner_id": learner.id,
                "name": learner.full_name,
                "adm_no": learner.adm_no,
                "days": r["total"],
                "present": r["present"],
                "absent": r["absent"],
                "rate": rate,
                "consecutive_absences": streak,
                "chronic": (rate is not None and rate < CHRONIC_RATE) or streak >= CONSECUTIVE_ABSENCES,
            }
        )
    return result


def consecutive_absences(learner, term):
    statuses = (
        AttendanceRecord.objects.filter(learner=learner, session__term=term, session__slot__isnull=True)
        .order_by("-session__date")
        .values_list("status", flat=True)[:30]
    )
    streak = 0
    for status in statuses:
        if status != "absent":
            break
        streak += 1
    return streak
