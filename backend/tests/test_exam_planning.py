"""Automatic exam timetables and mixed seating plans."""

import datetime
from collections import Counter, defaultdict

import pytest

from apps.assessment.models import Exam, ExamSchedule, ExamSeat
from apps.timetable.models import Room

from .factories import LearnerFactory, StaffFactory, enrol

pytestmark = pytest.mark.django_db


def _next_monday(day):
    return day + datetime.timedelta(days=(7 - day.weekday()) % 7 or 7)


@pytest.fixture
def end_of_term(school, term, p5, today):
    p6 = p5.next_class
    exam = Exam.objects.create(school=school, term=term, name="End of Term", kind="eot", weight=100)
    exam.classes.add(p5, p6)
    for school_class, count in ((p5, 5), (p6, 4)):
        for _ in range(count):
            enrol(LearnerFactory(school=school), term, school_class)
    for _ in range(6):
        StaffFactory(school=school, kind="teaching")
    return exam, p5, p6


def test_exam_timetable_is_generated(school, end_of_term, dos, client_for):
    exam, p5, p6 = end_of_term
    monday = _next_monday(datetime.date.today())
    friday = monday + datetime.timedelta(days=4)
    url = f"/api/exams/{exam.id}/generate-timetable/"
    result = (
        client_for(dos)
        .post(
            url,
            {
                "start_date": monday.isoformat(),
                "end_date": (friday + datetime.timedelta(days=3)).isoformat(),
                "max_per_day": 2,
            },
            format="json",
        )
        .json()
    )
    assert result["created"] > 0 and not result["unplaced"], result
    rows = list(ExamSchedule.objects.filter(exam=exam))
    # School days only, at most two papers a day per class, one paper per class per session.
    assert all(r.date.weekday() < 5 for r in rows)
    per_day = Counter((r.school_class_id, r.date) for r in rows)
    assert max(per_day.values()) <= 2
    assert len({(r.school_class_id, r.date, r.start_time) for r in rows}) == len(rows)
    # A paper both classes take is sat at the same time.
    by_subject = defaultdict(set)
    for r in rows:
        by_subject[(r.subject_id, r.paper_id)].add((r.date, r.start_time))
    assert all(len(times) == 1 for times in by_subject.values())
    # Invigilators are never in two places at once.
    duty = Counter((r.invigilator_id, r.date, r.start_time) for r in rows if r.invigilator_id)
    assert max(duty.values()) == 1

    # Too few days: what does not fit is reported, not squeezed in.
    tight = (
        client_for(dos)
        .post(
            url,
            {"start_date": monday.isoformat(), "end_date": monday.isoformat(), "replace": True},
            format="json",
        )
        .json()
    )
    assert tight["unplaced"] and tight["advice"]


def test_mixed_seating_plan(school, end_of_term, dos, client_for):
    exam, p5, p6 = end_of_term
    monday = _next_monday(datetime.date.today())
    client = client_for(dos)
    client.post(
        f"/api/exams/{exam.id}/generate-timetable/",
        {"start_date": monday.isoformat(), "end_date": (monday + datetime.timedelta(days=11)).isoformat()},
        format="json",
    )
    hall = Room.objects.create(school=school, name="Hall", capacity=6)
    lab = Room.objects.create(school=school, name="Lab", capacity=6)
    small = Room.objects.create(school=school, name="Store", capacity=3)
    refused = client.post(f"/api/exams/{exam.id}/seating/", {"rooms": [small.id]}, format="json")
    assert refused.status_code == 400 and "hold 3" in str(refused.json())

    summary = client.post(
        f"/api/exams/{exam.id}/seating/", {"rooms": [hall.id, lab.id]}, format="json"
    ).json()
    both = next(s for s in summary if s["learners"] == 9)  # a paper P5 and P6 both sit
    date, start = both["date"], both["start_time"]
    seats = list(
        ExamSeat.objects.filter(exam=exam, date=date, start_time=start).order_by("room__name", "seat")
    )
    assert len(seats) == 9 and len({s.learner_id for s in seats}) == 9
    hall_seats = [s for s in seats if s.room_id == hall.id]
    neighbours_same = sum(
        1 for a, b in zip(hall_seats, hall_seats[1:], strict=False) if a.school_class_id == b.school_class_id
    )
    assert neighbours_same == 0
    pdf = client.get(f"/api/exams/{exam.id}/seating-pdf/", {"date": date, "start_time": start})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    listing = client.get(f"/api/exams/{exam.id}/seating/").json()
    assert any(row["seated"] == 9 for row in listing)
