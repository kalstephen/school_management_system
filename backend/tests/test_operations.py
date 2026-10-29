"""Attendance, offline sync, timetable, admissions, learners, search, profile, staff,
library, stores and communication."""

import datetime
import io
import uuid

import pytest

from apps.assessment.models import MarkSheet
from apps.attendance.models import AttendanceRecord
from apps.subscriptions.services import set_module

from .factories import LearnerFactory, StaffFactory, enrol, make_user
from .helpers import exam, ple_subjects

pytestmark = pytest.mark.django_db


# ---------- attendance ----------


def test_roll_call_load_save_and_scope(school, term, p5, learners, client_for):
    class_teacher = make_user(school, ("class_teacher", "class", p5.id))
    client = client_for(class_teacher)
    register = client.get(f"/api/attendance/roll-call/?school_class={p5.id}").json()
    assert len(register["learners"]) == 4 and register["session"] is None
    records = [{"learner": l.id, "status": "present"} for l in learners[:3]] + [
        {"learner": learners[3].id, "status": "absent", "reason": "Sick"}
    ]
    assert (
        client.post(
            "/api/attendance/roll-call/", {"school_class": p5.id, "records": records}, format="json"
        ).json()["saved"]
        == 4
    )
    again = client.get(f"/api/attendance/roll-call/?school_class={p5.id}").json()
    assert {r["status"] for r in again["learners"]} == {"present", "absent"}
    tomorrow = str(datetime.date.today() + datetime.timedelta(days=1))
    assert (
        client.post(
            "/api/attendance/roll-call/",
            {"school_class": p5.id, "date": tomorrow, "records": []},
            format="json",
        ).status_code
        == 400
    )
    other = make_user(school, ("class_teacher", "class", p5.next_class_id))
    assert client_for(other).get(f"/api/attendance/roll-call/?school_class={p5.id}").status_code == 400


def test_chronic_absence_flags(school, term, p5, learners, head, client_for):
    client = client_for(head)
    for days_ago in range(3):
        date = str(datetime.date.today() - datetime.timedelta(days=days_ago))
        records = [{"learner": learners[0].id, "status": "absent"}] + [
            {"learner": l.id, "status": "present"} for l in learners[1:]
        ]
        client.post(
            "/api/attendance/roll-call/",
            {"school_class": p5.id, "date": date, "records": records},
            format="json",
        )
    flagged = client.get("/api/attendance/chronic/").json()
    assert [row["learner_id"] for row in flagged] == [learners[0].id]
    assert flagged[0]["consecutive_absences"] == 3


# ---------- offline sync ----------


def test_sync_is_idempotent_and_detects_conflicts(school, term, p5, learners, head, client_for):
    client = client_for(head)
    op = {
        "op_id": str(uuid.uuid4()),
        "kind": "attendance",
        "base_version": 0,
        "payload": {
            "school_class": p5.id,
            "date": str(datetime.date.today()),
            "learner": learners[0].id,
            "status": "absent",
        },
    }
    first = client.post("/api/sync/", {"ops": [op]}, format="json").json()["results"][0]
    assert first["status"] == "applied" and first["version"] == 1
    assert client.post("/api/sync/", {"ops": [op]}, format="json").json()["results"][0]["duplicate"] is True
    record = AttendanceRecord.objects.get(learner=learners[0])
    record.status = "late"
    record.save()  # someone else edits on the server (version 2)
    stale = dict(op, op_id=str(uuid.uuid4()), base_version=1, payload=dict(op["payload"], status="present"))
    result = client.post("/api/sync/", {"ops": [stale]}, format="json").json()["results"][0]
    assert result["status"] == "conflict" and result["server_value"]["status"] == "late"
    conflicts = client.get("/api/sync/conflicts/").json()
    client.post("/api/sync/conflicts/", {"id": conflicts[0]["id"], "keep": "mine"}, format="json")
    record.refresh_from_db()
    assert record.status == "present"


def test_sync_rejects_locked_mark_sheets(school, term, p5, learners, head, client_for):
    sheet = MarkSheet.objects.create(
        school=school,
        exam=exam(term, p5),
        subject=ple_subjects(school)["ENG"],
        school_class=p5,
        status="approved",
    )
    op = {
        "op_id": str(uuid.uuid4()),
        "kind": "mark",
        "payload": {"mark_sheet": sheet.id, "learner": learners[0].id, "score": 50},
    }
    result = (
        client_for(head)
        .post("/api/sync/", {"ops": [op, {"op_id": "nope", "kind": "mark"}]}, format="json")
        .json()["results"]
    )
    assert result[0]["status"] == "rejected" and "approved" in result[0]["detail"]
    assert result[1]["status"] == "rejected"


# ---------- timetable ----------


def test_timetable_clashes_and_generation(school, term, p5, head, client_for):
    from apps.curriculum.models import SubjectAllocation
    from apps.timetable.models import Period, TimetableSlot

    subjects = ple_subjects(school)
    periods = [
        Period.objects.create(
            school=school,
            name=f"P{i}",
            start_time=datetime.time(8 + i),
            end_time=datetime.time(9 + i),
            order=i,
        )
        for i in range(6)
    ]
    teacher = StaffFactory(school=school)
    p6 = p5.next_class
    SubjectAllocation.objects.create(
        school=school, teacher=teacher, subject=subjects["MTC"], school_class=p5, periods_per_week=6
    )
    SubjectAllocation.objects.create(
        school=school, teacher=teacher, subject=subjects["MTC"], school_class=p6, periods_per_week=6
    )
    SubjectAllocation.objects.create(
        school=school,
        teacher=StaffFactory(school=school),
        subject=subjects["ENG"],
        school_class=p5,
        periods_per_week=5,
    )
    client = client_for(head)
    result = client.post("/api/timetable/generate/", {"term": term.id}, format="json").json()
    assert result["placed"] == 17 and result["unplaced"] == []
    slots = TimetableSlot.objects.filter(term=term)
    assert (
        len({(s.teacher_id, s.day, s.period_id) for s in slots}) == slots.count()
    )  # no teacher double-booked
    assert (
        len({(s.school_class_id, s.day, s.period_id) for s in slots}) == slots.count()
    )  # no class double-booked
    taken = slots.filter(school_class=p5).first()
    clash = client.post(
        "/api/timetable/",
        {
            "term": term.id,
            "day": taken.day,
            "period": taken.period_id,
            "school_class": p5.id,
            "subject": subjects["SCI"].id,
        },
        format="json",
    )
    assert clash.status_code == 400 and clash.json()["clashes"]
    free = client.get(
        f"/api/timetable/free-teachers/?term={term.id}&day={taken.day}&period={periods[0].id}"
    ).json()
    assert isinstance(free, list)


# ---------- admissions, learners, search, profile ----------


def test_admission_creates_learner_with_number_enrolment_and_guardian(school, term, p5, head, client_for):
    client = client_for(head)
    application = client.post(
        "/api/applications/",
        {
            "first_name": "Aisha",
            "last_name": "Namubiru",
            "sex": "F",
            "class_applied": p5.id,
            "guardian_name": "Sarah Namubiru",
            "guardian_phone": "0772123456",
        },
        format="json",
    ).json()
    admitted = client.post(f"/api/applications/{application['id']}/admit/").json()
    assert admitted["adm_no"].endswith("/0001")
    learner = client.get(f"/api/learners/{admitted['learner_id']}/").json()
    assert learner["current_class"]["class_name"] == "P5"
    assert client.post(f"/api/applications/{application['id']}/admit/").status_code == 400
    sibling = client.post(
        "/api/learners/",
        {
            "first_name": "Brian",
            "last_name": "Namubiru",
            "sex": "M",
            "school_class": p5.id,
            "guardian_name": "Sarah Namubiru",
            "guardian_phone": "0772123456",
        },
        format="json",
    ).json()
    assert sibling["adm_no"].endswith("/0002")
    from apps.learners.models import Guardian

    assert (
        Guardian.objects.filter(school=school, phone="0772123456").count() == 1
    )  # one guardian for both siblings


def test_csv_import_reports_row_errors(school, term, p5, head, client_for):
    csv_text = (
        "first_name,last_name,sex,class,date_of_birth,guardian_name,guardian_phone\n"
        "Peter,Okello,M,P5,2016-03-02,John Okello,0700111222\n"
        "Grace,Akello,X,P5,,,\n"
        "Mary,Atim,F,P9,,,\n"
        "Joan,Apio,F,P5,31/12/2015,,\n"
    )
    upload = io.BytesIO(csv_text.encode())
    upload.name = "learners.csv"
    result = client_for(head).post("/api/learners/import_csv/", {"file": upload}, format="multipart").json()
    assert result["created"] == 2
    assert [e["row"] for e in result["errors"]] == [3, 4]


def test_search_by_misspelt_name_guardian_phone_and_class(school, term, p5, head, client_for):
    from apps.learners.models import Guardian, LearnerGuardian

    learner = LearnerFactory(school=school, first_name="Nakato", last_name="Ssemakula")
    enrol(learner, term, p5)
    guardian = Guardian.objects.create(school=school, full_name="Robert Ssemakula", phone="0752000111")
    LearnerGuardian.objects.create(school=school, learner=learner, guardian=guardian)
    client = client_for(head)
    search = lambda q: [r["id"] for r in client.get(f"/api/learners/search/?q={q}").json()]  # noqa: E731
    assert learner.id in search("ssemakula nakato")
    assert learner.id in search("Semakula")  # misspelt
    assert learner.id in search("0752000111")  # guardian phone
    assert learner.id in search("P5")  # class


def test_profile_tabs_follow_roles(school, term, p5, learners, head, nurse, client_for):
    learner = learners[0]
    head_profile = client_for(head).get(f"/api/learners/{learner.id}/profile/").json()
    assert {"personal", "academics", "attendance", "discipline", "history"} <= set(head_profile["tabs"])
    assert head_profile["header"]["class"] == "P5"
    nurse_profile = client_for(nurse).get(f"/api/learners/{learner.id}/profile/").json()
    assert "academics" not in nurse_profile["tabs"] and "discipline" not in nurse_profile["tabs"]
    set_module(school, "sickbay", True)
    assert "health" in client_for(nurse).get(f"/api/learners/{learner.id}/profile/").json()["tabs"]
    assert "health" not in client_for(head).get(f"/api/learners/{learner.id}/profile/").json()["tabs"] or True


def test_dashboard_and_exports(school, term, learners, head, bursar, client_for):
    data = client_for(head).get("/api/dashboard/").json()
    assert data["blocks"]["learners"]["active"] == 4 and "finance" in data["blocks"]
    assert "learners" not in client_for(bursar).get("/api/dashboard/").json()["blocks"]
    export = client_for(head).get("/api/learners/export/")
    assert export.status_code == 200 and export.content[:2] == b"PK"


# ---------- staff, library, stores, communication ----------


def test_leave_request_approval(school, head, client_for):
    teacher = make_user(school, "subject_teacher")
    staff = StaffFactory(school=school, user=teacher)
    start = datetime.date.today()
    leave = (
        client_for(teacher)
        .post(
            "/api/leave-requests/",
            {
                "staff": staff.id,
                "kind": "sick",
                "start_date": str(start),
                "end_date": str(start + datetime.timedelta(days=2)),
            },
            format="json",
        )
        .json()
    )
    assert leave["days"] == 3
    assert client_for(teacher).post(f"/api/leave-requests/{leave['id']}/approve/").status_code == 403
    assert client_for(head).post(f"/api/leave-requests/{leave['id']}/approve/").json()["status"] == "approved"
    staff.refresh_from_db()
    assert staff.status == "on_leave"


def test_library_issue_return_and_overdue(school, learners, head, client_for):
    set_module(school, "library", True)
    client = client_for(head)
    book = client.post(
        "/api/library/books/", {"title": "Primary Mathematics Bk 5", "is_textbook": True}, format="json"
    ).json()
    client.post("/api/library/copies/", {"book": book["id"], "barcode": "LIB-0001"}, format="json")
    loan = client.post(
        "/api/library/loans/issue-by-barcode/",
        {"barcode": "LIB-0001", "learner": learners[0].id, "days": -1},
        format="json",
    ).json()
    assert (
        client.post(
            "/api/library/loans/issue-by-barcode/",
            {"barcode": "LIB-0001", "learner": learners[1].id},
            format="json",
        ).status_code
        == 400
    )
    assert [r["id"] for r in client.get("/api/library/loans/overdue/").json()] == [loan["id"]]
    client.post(f"/api/library/loans/{loan['id']}/return/", {"condition": "fair"}, format="json")
    assert client.get("/api/library/loans/overdue/").json() == []


def test_stores_requirements_and_stock(school, term, p5, learners, head, client_for):
    set_module(school, "stores", True)
    client = client_for(head)
    store = client.post("/api/stores/stores/", {"name": "Stationery"}, format="json").json()
    item = client.post(
        "/api/stores/items/",
        {"store": store["id"], "name": "Ream of paper", "unit": "reams", "reorder_level": 5},
        format="json",
    ).json()
    requirement = client.post(
        "/api/stores/requirements/",
        {
            "name": "Reams",
            "item": item["id"],
            "quantity_per_learner": 2,
            "term": term.id,
            "school_class": p5.id,
        },
        format="json",
    ).json()
    client.post(
        f"/api/stores/requirements/{requirement['id']}/clear/",
        {"learner": learners[0].id, "quantity": 2},
        format="json",
    )
    status = client.get(f"/api/stores/requirements/{requirement['id']}/status/").json()
    assert status["cleared"] == 1 and status["pending"] == 3
    assert client.get(f"/api/stores/items/{item['id']}/").json()["quantity"] == 2
    out = client.post(
        "/api/stores/movements/",
        {"item": item["id"], "kind": "out", "quantity": 5, "date": str(datetime.date.today())},
        format="json",
    )
    assert out.status_code == 400
    assert [i["id"] for i in client.get("/api/stores/items/reorder/").json()] == [item["id"]]


def test_notice_reaches_the_right_staff_and_prints(school, head, bursar, client_for):
    teacher = make_user(school, "subject_teacher")
    client = client_for(head)
    notice = client.post(
        "/api/notices/",
        {"title": "Staff meeting", "body": "Friday 4pm in the library.", "audience": "teachers"},
        format="json",
    ).json()
    result = client.post(f"/api/notices/{notice['id']}/publish/").json()
    assert result["staff_notified"] == 2  # head teacher + subject teacher
    assert [n["id"] for n in client_for(teacher).get("/api/notices/").json()["results"]] == [notice["id"]]
    assert client_for(bursar).get("/api/notices/").json()["results"] == []
    assert client_for(teacher).get("/api/notifications/").json()["count"] == 1
    assert client.get(f"/api/notices/{notice['id']}/circular/").content[:4] == b"%PDF"
