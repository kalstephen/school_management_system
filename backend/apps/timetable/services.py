from django.db import transaction
from django.db.models import Q

from apps.curriculum.models import SubjectAllocation
from apps.staff.models import LeaveRequest, StaffProfile

from .models import Period, TimetableSlot

SCHOOL_DAYS = (1, 2, 3, 4, 5)


def find_clashes(school, term, day, period, school_class, stream, teacher, room, exclude_pk=None):
    """Return human-readable clashes for a proposed slot (teacher, room or class double-booked)."""
    same_time = TimetableSlot.objects.filter(school=school, term=term, day=day, period=period)
    if exclude_pk:
        same_time = same_time.exclude(pk=exclude_pk)
    clashes = []
    if teacher and same_time.filter(teacher=teacher).exists():
        clashes.append(f"{teacher} already teaches at this time.")
    if room and same_time.filter(room=room).exists():
        clashes.append(f"{room} is already in use at this time.")
    class_slots = same_time.filter(school_class=school_class)
    if stream is not None:
        class_slots = class_slots.filter(Q(stream=stream) | Q(stream__isnull=True))
    if class_slots.exists():
        clashes.append(f"{stream or school_class} already has a lesson at this time.")
    return clashes


def generate_timetable(school, term, class_ids=None, days=SCHOOL_DAYS):
    """Rule-based generation: spread each allocation's weekly periods across the week,
    at most one lesson of a subject per day where possible, avoiding all clashes.
    Existing slots for the chosen classes are replaced. Returns placed and unplaced counts."""
    periods = list(Period.objects.filter(school=school, is_break=False).order_by("order"))
    allocations = SubjectAllocation.objects.filter(school=school).select_related(
        "teacher", "school_class", "stream"
    )
    if class_ids:
        allocations = allocations.filter(school_class_id__in=class_ids)
    allocations = sorted(allocations, key=lambda a: -a.periods_per_week)
    unplaced = []
    placed = 0
    with transaction.atomic():
        old = TimetableSlot.objects.filter(school=school, term=term)
        if class_ids:
            old = old.filter(school_class_id__in=class_ids)
        old.delete()
        teacher_busy, class_busy = set(), set()
        for slot in TimetableSlot.objects.filter(school=school, term=term):
            teacher_busy.add((slot.teacher_id, slot.day, slot.period_id))
            class_busy.add((slot.school_class_id, slot.stream_id, slot.day, slot.period_id))
        for alloc in allocations:
            remaining = alloc.periods_per_week
            used_days = []
            for pass_number in range(3):  # pass 0: one per day; later passes allow doubles
                for period in periods:
                    for day in days:
                        if remaining == 0:
                            break
                        if pass_number == 0 and day in used_days:
                            continue
                        if (alloc.teacher_id, day, period.id) in teacher_busy:
                            continue
                        stream_keys = {
                            (alloc.school_class_id, alloc.stream_id, day, period.id),
                            (alloc.school_class_id, None, day, period.id),
                        }
                        if alloc.stream_id is None:
                            if any(
                                k[0] == alloc.school_class_id and k[2] == day and k[3] == period.id
                                for k in class_busy
                            ):
                                continue
                        elif stream_keys & class_busy:
                            continue
                        TimetableSlot.objects.create(
                            school=school,
                            term=term,
                            day=day,
                            period=period,
                            school_class=alloc.school_class,
                            stream=alloc.stream,
                            subject=alloc.subject,
                            teacher=alloc.teacher,
                        )
                        teacher_busy.add((alloc.teacher_id, day, period.id))
                        class_busy.add((alloc.school_class_id, alloc.stream_id, day, period.id))
                        used_days.append(day)
                        remaining -= 1
                        placed += 1
                if remaining == 0:
                    break
            if remaining:
                unplaced.append(
                    {
                        "allocation": alloc.id,
                        "subject": str(alloc.subject),
                        "class": str(alloc.stream or alloc.school_class),
                        "missing_periods": remaining,
                    }
                )
    return {"placed": placed, "unplaced": unplaced}


def free_teachers(school, term, day, period, on_date):
    """Teachers with no lesson at this time and not on approved leave that day — substitution candidates."""
    busy = TimetableSlot.objects.filter(school=school, term=term, day=day, period=period).values("teacher_id")
    on_leave = LeaveRequest.objects.filter(
        school=school, status=LeaveRequest.Status.APPROVED, start_date__lte=on_date, end_date__gte=on_date
    ).values("staff_id")
    return (
        StaffProfile.objects.filter(
            school=school, kind=StaffProfile.Kind.TEACHING, status=StaffProfile.Status.ACTIVE
        )
        .exclude(pk__in=busy)
        .exclude(pk__in=on_leave)
    )
