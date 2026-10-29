"""Exam timetables made automatically, and mixed seating plans.

Timetable: every paper the exam's classes sit is placed in a session (e.g. 08:30–10:30)
on a school day between the exam's dates. A paper is sat by all its classes at the same time
(fair, and it lets classes share rooms), no class sits more than a set number of papers a
day, and each class gets an invigilator who does not teach it that subject and is free.

Seating: for one session, every learner sitting it is seated across the chosen rooms with the
classes interleaved, so neighbours come from different classes and streams.
"""

import datetime
import random
from collections import defaultdict

from django.db import transaction

from apps.core.exceptions import BusinessRuleError

DEFAULT_SESSIONS = [("08:30", "10:30"), ("11:00", "13:00"), ("14:00", "16:00")]
DEFAULT_ROOM_SIZE = 40


def _time(value):
    return value if isinstance(value, datetime.time) else datetime.time.fromisoformat(str(value))


def exam_days(exam, start=None, end=None):
    """School days between the dates (weekends, public holidays and closures skipped)."""
    from apps.schoolsetup.calendar import calendar_days

    start = start or exam.start_date
    end = end or exam.end_date
    if not start or not end:
        raise BusinessRuleError({"start_date": "Give the exam's first and last day."})
    if end < start:
        raise BusinessRuleError({"end_date": "The last day must be on or after the first."})
    days = [d["date"] for d in calendar_days(exam.school, start, end) if d["school_day"]]
    if not days:
        raise BusinessRuleError({"start_date": "There are no school days between those dates."})
    return days


def generate_exam_timetable(exam, start=None, end=None, sessions=None, max_per_day=2, replace=False):
    from apps.curriculum.models import SubjectAllocation
    from apps.staff.models import StaffProfile

    from .grading import subjects_offered
    from .models import ExamSchedule

    days = exam_days(exam, start, end)
    sessions = [(_time(a), _time(b)) for a, b in (sessions or DEFAULT_SESSIONS)]
    if not sessions:
        raise BusinessRuleError({"sessions": "Choose at least one session."})
    max_per_day = max(1, int(max_per_day or 2))
    classes = list(exam.classes.select_related("section").order_by("order"))
    if not classes:
        raise BusinessRuleError({"detail": "Tick the classes that sit this exam first."})

    # Each paper and the classes that sit it.
    papers = defaultdict(list)
    for school_class in classes:
        for subject in subjects_offered(school_class):
            for paper in list(subject.papers.all()) or [None]:
                papers[(subject, paper)].append(school_class)
    # Core and aggregate subjects first, then the rest, so the main papers get early slots.
    order = sorted(
        papers,
        key=lambda sp: (
            not sp[0].in_aggregate,
            sp[0].category != "core",
            sp[0].order,
            sp[0].name,
            sp[1].number if sp[1] else 0,
        ),
    )
    slots = [(day, s) for day in days for s in sessions]
    taken = defaultdict(set)  # slot -> class ids sitting something
    per_day = defaultdict(int)  # (class id, day) -> papers that day
    existing = set()
    with transaction.atomic():
        if replace:
            exam.schedule.all().delete()
        else:
            for row in exam.schedule.all():
                slot = (row.date, (row.start_time, row.end_time))
                taken[slot].add(row.school_class_id)
                per_day[(row.school_class_id, row.date)] += 1
                existing.add((row.subject_id, row.paper_id, row.school_class_id))

        teaching = defaultdict(set)  # (subject, class) -> teacher ids who teach it
        for alloc in SubjectAllocation.objects.filter(school=exam.school):
            teaching[(alloc.subject_id, alloc.school_class_id)].add(alloc.teacher_id)
        staff = list(StaffProfile.objects.filter(school=exam.school, kind="teaching", status="active"))
        busy = defaultdict(set)
        duties = defaultdict(int)
        for row in exam.schedule.exclude(invigilator=None):
            busy[(row.date, row.start_time)].add(row.invigilator_id)
            duties[row.invigilator_id] += 1

        created, unplaced = 0, []
        for subject, paper in order:
            sitting = [
                c
                for c in papers[(subject, paper)]
                if (subject.id, getattr(paper, "id", None), c.id) not in existing
            ]
            if not sitting:
                continue
            label = f"{subject.name}{f' P{paper.number}' if paper else ''}"
            slot = next(
                (
                    sl
                    for sl in slots
                    if not any(c.id in taken[sl] for c in sitting)
                    and all(per_day[(c.id, sl[0])] < max_per_day for c in sitting)
                ),
                None,
            )
            if slot is None:
                unplaced.append(f"{label} ({', '.join(c.name for c in sitting)})")
                continue
            day, (begins, ends) = slot
            for school_class in sitting:
                free = [
                    t
                    for t in staff
                    if t.id not in busy[(day, begins)] and t.id not in teaching[(subject.id, school_class.id)]
                ]
                invigilator = min(free, key=lambda t: duties[t.id]) if free else None
                if invigilator:
                    busy[(day, begins)].add(invigilator.id)
                    duties[invigilator.id] += 1
                ExamSchedule.objects.create(
                    school=exam.school,
                    exam=exam,
                    subject=subject,
                    paper=paper,
                    school_class=school_class,
                    date=day,
                    start_time=begins,
                    end_time=ends,
                    invigilator=invigilator,
                )
                taken[slot].add(school_class.id)
                per_day[(school_class.id, day)] += 1
                created += 1
    return {
        "created": created,
        "unplaced": unplaced,
        "days": [d.isoformat() for d in days],
        "advice": (
            "Some papers did not fit: add exam days, add a session or allow more papers a day."
            if unplaced
            else ""
        ),
    }


def sessions_of(exam):
    """The distinct (date, start, end) sessions in the exam timetable."""
    return sorted({(r.date, r.start_time, r.end_time) for r in exam.schedule.all()})


def generate_seating(exam, rooms, sessions=None):
    """Seat each session's learners across the rooms, classes interleaved. Replaces any earlier
    plan for those sessions. Returns a summary per session."""
    from apps.learners.models import Enrolment

    from .models import ExamSeat

    if not rooms:
        raise BusinessRuleError({"rooms": "Choose the rooms learners sit in."})
    wanted = sessions_of(exam)
    if sessions:
        keys = {(str(s.get("date")), str(s.get("start_time"))[:5]) for s in sessions}
        wanted = [s for s in wanted if (s[0].isoformat(), s[1].strftime("%H:%M")) in keys]
    if not wanted:
        raise BusinessRuleError({"detail": "Make the exam timetable first."})
    capacity = sum(r.capacity or DEFAULT_ROOM_SIZE for r in rooms)
    summary = []
    rng = random.Random(f"seating-{exam.pk}")
    with transaction.atomic():
        for date, begins, ends in wanted:
            rows = exam.schedule.filter(date=date, start_time=begins).select_related("school_class")
            groups = []
            for row in rows:
                enrolments = Enrolment.objects.filter(
                    term=exam.term, school_class=row.school_class, learner__status="active"
                ).select_related("learner", "stream")
                by_stream = defaultdict(list)
                for e in enrolments:
                    by_stream[e.stream_id].append(e.learner)
                # Each stream is its own group, so streams of one class alternate too.
                for learners in by_stream.values():
                    rng.shuffle(learners)
                    groups.append((row.school_class, learners))
            # Round-robin over classes so neighbours differ.
            queue, seen = [], set()
            longest = max((len(g[1]) for g in groups), default=0)
            for i in range(longest):
                for school_class, learners in groups:
                    if i < len(learners) and learners[i].id not in seen:
                        queue.append((learners[i], school_class))
                        seen.add(learners[i].id)
            if len(queue) > capacity:
                raise BusinessRuleError(
                    {
                        "rooms": f"{len(queue)} learners sit on {date:%a %d %b} at {begins:%H:%M} "
                        f"but the rooms hold {capacity}. Add rooms or set their capacity."
                    }
                )
            ExamSeat.objects.filter(exam=exam, date=date, start_time=begins).delete()
            position = 0
            per_room = []
            for room in rooms:
                size = room.capacity or DEFAULT_ROOM_SIZE
                chunk = queue[position : position + size]
                position += len(chunk)
                for seat, (learner, school_class) in enumerate(chunk, start=1):
                    ExamSeat.objects.create(
                        school=exam.school,
                        exam=exam,
                        date=date,
                        start_time=begins,
                        end_time=ends,
                        learner=learner,
                        school_class=school_class,
                        room=room,
                        seat=seat,
                    )
                if chunk:
                    per_room.append({"room": room.name, "learners": len(chunk)})
            summary.append(
                {
                    "date": date,
                    "start_time": begins.strftime("%H:%M"),
                    "papers": sorted({str(r.subject) for r in rows}),
                    "learners": len(queue),
                    "rooms": per_room,
                }
            )
    return summary
