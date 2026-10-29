"""Class set-up, grading presets, Excel enrolment, teacher logins, the weekly planner,
published timetables and report card designs."""

import datetime
import io

import pytest
from openpyxl import load_workbook

from apps.accounts.models import RoleAssignment
from apps.learners.models import Enrolment, Learner
from apps.schoolsetup.models import GradingScale, SchoolClass, Stream, Term

from .factories import StaffFactory, make_user
from .helpers import exam, ple_subjects

pytestmark = pytest.mark.django_db


# ---------- classes and streams ----------


def test_class_with_streams_and_class_teacher(school, head, setup_client, client_for):
    # The school cannot create classes; the owner console does.
    assert client_for(head).post("/api/classes/", {"name": "P8"}, format="json").status_code == 403
    client = setup_client
    section = SchoolClass.objects.get(school=school, name="P5").section
    teacher_user = make_user(school, "subject_teacher")
    teacher = StaffFactory(school=school, user=teacher_user)
    response = client.post(
        "/api/classes/",
        {
            "section": section.id,
            "name": "P8",
            "order": 99,
            "stream_names": ["East", "West", " "],
            "class_teacher": teacher.id,
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    new_class = SchoolClass.objects.get(pk=response.json()["id"])
    assert sorted(new_class.streams.values_list("name", flat=True)) == ["East", "West"]
    assert RoleAssignment.objects.filter(
        membership__user=teacher_user, role="class_teacher", scope_type="class", scope_id=new_class.id
    ).exists()

    # The school chooses the class teacher; the access moves with the job.
    other_user = make_user(school, "subject_teacher")
    other = StaffFactory(school=school, user=other_user)
    assert (
        client_for(teacher_user)
        .post(f"/api/classes/{new_class.id}/class-teacher/", {"class_teacher": other.id}, format="json")
        .status_code
        == 403
    )
    assigned = client_for(head).post(
        f"/api/classes/{new_class.id}/class-teacher/", {"class_teacher": other.id}, format="json"
    )
    assert assigned.json()["class_teacher_name"] == other.full_name
    assert not RoleAssignment.objects.filter(membership__user=teacher_user, role="class_teacher").exists()
    assert RoleAssignment.objects.filter(membership__user=other_user, scope_id=new_class.id).exists()

    duplicate = client.post(
        "/api/classes/",
        {"section": section.id, "name": "P9", "order": 100, "stream_names": ["Blue", "blue"]},
        format="json",
    )
    assert duplicate.status_code == 400


def test_candidate_class_does_not_promote(school, p7, p5, setup_client):
    response = setup_client.patch(
        f"/api/classes/{p7.id}/", {"is_candidate_class": True, "next_class": p5.id}, format="json"
    )
    assert response.status_code == 400 and "next_class" in str(response.json())


# ---------- grading ----------


def test_grading_presets_and_custom_bands(school, dos, client_for):
    client = client_for(dos)
    presets = client.get("/api/grading-scales/presets/").json()
    assert {"ple", "cbc", "uace", "uce_old"} <= {p["key"] for p in presets}
    scale = GradingScale.objects.filter(school=school).first()

    applied = client.post(f"/api/grading-scales/{scale.id}/set-bands/", {"preset": "ple"}, format="json")
    assert applied.status_code == 200
    assert {b["label"] for b in applied.json()["bands"]} >= {"D1", "F9"}

    # The DOS sets the school's own cut-offs.
    bands = [
        {"label": "A", "min_score": 80, "max_score": 100, "points": 1},
        {"label": "B", "min_score": 60, "max_score": 79.99, "points": 2},
        {"label": "C", "min_score": 0, "max_score": 59.99, "points": 3},
    ]
    assert (
        client.post(f"/api/grading-scales/{scale.id}/set-bands/", {"bands": bands}, format="json").status_code
        == 200
    )
    assert scale.bands.count() == 3

    gap = [dict(bands[0]), dict(bands[2])]
    bad = client.post(f"/api/grading-scales/{scale.id}/set-bands/", {"bands": gap}, format="json")
    assert bad.status_code == 400 and scale.bands.count() == 3
    overlap = [dict(bands[0], min_score=70), bands[1], bands[2]]
    assert (
        client.post(
            f"/api/grading-scales/{scale.id}/set-bands/", {"bands": overlap}, format="json"
        ).status_code
        == 400
    )


def test_teachers_cannot_change_grading(school, teacher_factory, client_for):
    scale = GradingScale.objects.filter(school=school).first()
    teacher = teacher_factory()
    response = client_for(teacher).post(
        f"/api/grading-scales/{scale.id}/set-bands/", {"preset": "ple"}, format="json"
    )
    assert response.status_code == 403


# ---------- Excel enrolment ----------


def _filled_template(client, rows):
    content = client.get("/api/learners/excel-template/").content
    book = load_workbook(io.BytesIO(content))
    sheet = book["Learners"]
    headers = [c.value.replace(" *", "") for c in sheet[1]]
    sheet.delete_rows(2)
    for row in rows:
        sheet.append([row.get(h, "") for h in headers])
    out = io.BytesIO()
    book.save(out)
    out.seek(0)
    out.name = "learners.xlsx"
    return out


def test_excel_import_checks_then_enrols(school, term, p5, head, client_for):
    client = client_for(head)
    stream = Stream.objects.create(school=school, school_class=p5, name="East")
    rows = [
        {
            "First name": "Aisha",
            "Surname": "Namubiru",
            "Sex (M/F)": "F",
            "Date of birth": "2016-05-14",
            "Father's name": "John Namubiru",
            "Father's phone": "0772123456",
            "Mother's name": "Sarah Nakato",
            "Mother's phone": "0701234567",
            "Illness / medical conditions": "Asthma",
        },
        {
            "First name": "Brian",
            "Surname": "Namubiru",
            "Sex (M/F)": "M",
            "Father's name": "John Namubiru",
            "Father's phone": "0772123456",
        },
        {"First name": "", "Surname": "Nobody", "Sex (M/F)": "X"},
    ]
    form = {"term": term.id, "school_class": p5.id, "stream": stream.id}
    check = client.post(
        "/api/learners/import-excel/", {**form, "dry_run": "true", "file": _filled_template(client, rows)}
    ).json()
    assert check["valid"] == 2 and len(check["errors"]) == 1 and check["created"] == 0
    assert Learner.objects.filter(school=school).count() == 0

    done = client.post("/api/learners/import-excel/", {**form, "file": _filled_template(client, rows)}).json()
    assert done["created"] == 2
    aisha = Learner.objects.get(school=school, first_name="Aisha")
    assert aisha.has_medical_alert and aisha.adm_no
    assert Enrolment.objects.filter(term=term, school_class=p5, stream=stream).count() == 2
    # Siblings share one father record.
    brian = Learner.objects.get(school=school, first_name="Brian")
    assert set(aisha.guardian_links.values_list("guardian__phone", flat=True)) >= {"0772123456"}
    assert (
        brian.guardian_links.get().guardian_id == aisha.guardian_links.get(relationship="Father").guardian_id
    )


def test_excel_import_needs_class_and_term(school, term, head, client_for):
    client = client_for(head)
    response = client.post("/api/learners/import-excel/", {"file": _filled_template(client, [])})
    assert response.status_code == 400


# ---------- teachers ----------


def test_add_teacher_with_login(school, head, client_for):
    client = client_for(head)
    response = client.post(
        "/api/staff/",
        {
            "first_name": "Grace",
            "last_name": "Akello",
            "kind": "teaching",
            "login_username": "gakello",
            "login_password": "Strong-Pass-2026",
            "login_role": "subject_teacher",
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["username"] == "gakello"
    # A head teacher cannot hand out the director's role.
    too_high = client.post(
        "/api/staff/",
        {
            "first_name": "X",
            "last_name": "Y",
            "kind": "teaching",
            "login_username": "xy",
            "login_password": "Strong-Pass-2026",
            "login_role": "director",
        },
        format="json",
    )
    assert too_high.status_code == 400


# ---------- planner ----------


def test_weekly_planner(school, head, client_for):
    teacher = make_user(school, "subject_teacher")
    StaffFactory(school=school, user=teacher)
    client = client_for(teacher)
    monday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
    last_week = str(monday - datetime.timedelta(days=7))
    for title in ("Mark P5 tests", "Prepare science notes"):
        assert (
            client.post(
                "/api/planner/", {"week_start": last_week, "day": 1, "title": title}, format="json"
            ).status_code
            == 201
        )
    first = client.get(f"/api/planner/?week_start={last_week}").json()[0]
    done = client.patch(f"/api/planner/{first['id']}/", {"done": True}, format="json").json()
    assert done["done"] and done["done_at"]
    assert (
        client.post("/api/planner/carry-over/", {"week_start": str(monday)}, format="json").json()["copied"]
        == 1
    )
    # The head teacher can look at the teacher's planner; other teachers cannot.
    assert len(client_for(head).get(f"/api/planner/?user={teacher.id}").json()) == 3
    stranger = make_user(school, "subject_teacher")
    assert client_for(stranger).get(f"/api/planner/?user={teacher.id}").json() == []


# ---------- published timetables ----------


def test_timetable_visible_after_publishing(school, term, p5, dos, client_for):
    from apps.timetable.models import Period, TimetableSlot

    subjects = ple_subjects(school)
    period = Period.objects.create(
        school=school, name="P1", start_time=datetime.time(8), end_time=datetime.time(9), order=1
    )
    teacher_user = make_user(school, "subject_teacher")
    teacher = StaffFactory(school=school, user=teacher_user)
    TimetableSlot.objects.create(
        school=school,
        term=term,
        day=1,
        period=period,
        school_class=p5,
        subject=subjects["MTC"],
        teacher=teacher,
    )
    teacher_client, dos_client = client_for(teacher_user), client_for(dos)
    assert teacher_client.get(f"/api/timetable/?term={term.id}").json() == []
    assert len(dos_client.get(f"/api/timetable/?term={term.id}").json()) == 1
    assert dos_client.post("/api/timetable/publish/", {"term": term.id}, format="json").status_code == 200
    assert len(teacher_client.get(f"/api/timetable/?term={term.id}&mine=1").json()) == 1
    assert teacher_client.post("/api/timetable/publish/", {"term": term.id}, format="json").status_code == 403
    pdf = teacher_client.get(f"/api/timetable/pdf/?term={term.id}&mine=1")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert dos_client.get(f"/api/timetable/pdf/?term={term.id}&school_class={p5.id}").content.startswith(
        b"%PDF"
    )


def test_exam_timetable_publish_and_weights(school, term, p5, dos, client_for):
    from apps.assessment.models import ExamSchedule

    subjects = ple_subjects(school)
    bot = exam(term, p5, kind="bot", weight=20)
    eot = exam(term, p5, kind="eot", weight=70)
    ExamSchedule.objects.create(
        school=school,
        exam=eot,
        subject=subjects["ENG"],
        school_class=p5,
        date=datetime.date.today(),
        start_time=datetime.time(9),
        end_time=datetime.time(11),
    )
    teacher = make_user(school, "subject_teacher")
    assert client_for(teacher).get(f"/api/exam-schedule/?exam={eot.id}").json()["count"] == 0
    dos_client = client_for(dos)
    assert dos_client.post(f"/api/exams/{bot.id}/publish-schedule/").status_code == 400  # nothing scheduled
    assert dos_client.post(f"/api/exams/{eot.id}/publish-schedule/").status_code == 200
    assert client_for(teacher).get(f"/api/exam-schedule/?exam={eot.id}").json()["count"] == 1
    assert client_for(teacher).get(f"/api/exams/{eot.id}/schedule-pdf/").content.startswith(b"%PDF")

    weights = dos_client.get(f"/api/exams/weights/?term={term.id}").json()
    row = next(r for r in weights if r["class_id"] == p5.id)
    assert row["total"] == 90 and row["ok"] is False


# ---------- report card designs ----------


def test_report_card_designs(school, head, setup_client, client_for):
    from apps.assessment.pdf import TEMPLATES, render_cards, sample_card

    for key in TEMPLATES:
        assert render_cards([sample_card(school)], key, "#047857").startswith(b"%PDF")
    client = client_for(head)
    assert client.get("/api/school/report-preview/?color=%23b91c1c").content.startswith(b"%PDF")
    # The colour, logo and profile are set in the owner console; the school only sees them.
    assert client.patch("/api/school/", {"report_color": "#b91c1c"}, format="json").status_code == 403
    setup_client.patch("/api/school/", {"report_color": "#b91c1c"}, format="json")
    school.refresh_from_db()
    assert school.report_color == "#b91c1c"


def test_admission_numbers_never_repeat(school, term, p5, setup_client):
    client = setup_client
    # An example typed into the pattern box instead of a pattern is refused...
    assert client.patch("/api/school/", {"adm_no_format": "2027/0001"}, format="json").status_code == 400
    # ...and one already stored falls back to the standard pattern.
    school.__class__.objects.filter(pk=school.pk).update(adm_no_format="2027/0001")
    school.refresh_from_db()
    numbers = {school.next_admission_number("2027") for _ in range(3)}
    assert len(numbers) == 3


# ---------- the owner console sets the school up ----------


def test_owner_console_changes_setup_but_never_reads_records(school, learners, setup_client):
    assert setup_client.get("/api/classes/").status_code == 200
    assert setup_client.patch("/api/school/", {"motto": "Light"}, format="json").status_code == 200
    # Learners, marks and finance stay closed to the platform team.
    assert setup_client.get("/api/learners/").status_code == 403
    assert setup_client.get("/api/finance/expenses/").status_code == 403
    assert setup_client.post("/api/staff/", {"first_name": "X"}, format="json").status_code == 403


def test_school_header_is_ignored_for_school_users(school, other_school, head, client_for):
    client = client_for(head)
    client.credentials(HTTP_X_SETUP_SCHOOL=str(other_school.id))
    rows = client.get("/api/classes/", {"page_size": 100}).json()["results"]
    assert {r["id"] for r in rows} == set(
        SchoolClass.objects.filter(school=school).values_list("id", flat=True)
    )
    assert client.post("/api/classes/", {"name": "X"}, format="json").status_code == 403


def test_generate_year_with_standard_terms(school, setup_client):
    from apps.schoolsetup.calendar import standard_terms

    response = setup_client.post("/api/setup/generate-year/", {"year": 2031}, format="json")
    assert response.json() == {"year": "2031", "terms_created": 3}
    terms = list(Term.objects.filter(school=school, academic_year__name="2031").order_by("number"))
    assert [(t.number, t.start_date, t.end_date) for t in terms] == standard_terms(2031)
    assert all(t.start_date.weekday() == 0 and t.end_date.weekday() == 4 for t in terms)
    assert terms[0].next_term_begins == terms[1].start_date
    # Running it again keeps the terms (and any dates adjusted since).
    again = setup_client.post("/api/setup/generate-year/", {"year": 2031}, format="json").json()
    assert again["terms_created"] == 0


def test_uganda_public_holidays():
    from apps.schoolsetup.calendar import public_holidays

    days = public_holidays(2026)
    assert days[datetime.date(2026, 10, 9)] == "Independence Day"
    assert days[datetime.date(2026, 6, 3)] == "Uganda Martyrs' Day"
    assert days[datetime.date(2026, 4, 3)] == "Good Friday"
    assert days[datetime.date(2026, 4, 6)] == "Easter Monday"


# ---------- daily register ----------


def _weekday_in_term(term, weekday):
    from apps.schoolsetup.calendar import public_holidays

    holidays = public_holidays(term.start_date.year) | public_holidays(term.end_date.year)
    day = term.start_date
    today = datetime.date.today()
    while day <= min(term.end_date, today):
        if day.weekday() == weekday and day not in holidays:
            return day
        day += datetime.timedelta(days=1)
    return None


def test_register_only_on_school_days(school, term, p5, learners, head, client_for):
    client = client_for(head)
    records = [{"learner": l.id, "status": "present"} for l in learners]
    saturday = _weekday_in_term(term, 5)
    response = client.post(
        "/api/attendance/roll-call/",
        {"school_class": p5.id, "date": saturday.isoformat(), "records": records},
        format="json",
    )
    assert response.status_code == 400 and "Weekend" in str(response.json())
    info = client.get("/api/attendance/roll-call/", {"school_class": p5.id, "date": saturday}).json()
    assert info["school_day"] is False

    monday = _weekday_in_term(term, 0)
    saved = client.post(
        "/api/attendance/roll-call/",
        {"school_class": p5.id, "date": monday.isoformat(), "records": records},
        format="json",
    )
    assert saved.status_code == 200
    register = client.get(
        "/api/attendance/register/", {"school_class": p5.id, "month": monday.strftime("%Y-%m")}
    ).json()
    assert register["learners"][0]["days"][monday.isoformat()] == "present"
    weekend = next(
        d for d in register["days"] if d["date"] == saturday.isoformat() or d["reason"] == "Weekend"
    )
    assert weekend["school_day"] is False
    assert monday.isoformat() not in [str(d) for d in register["missing"]]


# ---------- enrolment by the director, DOS and class teacher ----------


def test_class_teacher_enrols_into_own_class_only(school, term, p5, client_for):
    teacher = make_user(school, ("class_teacher", "class", p5.id))
    client = client_for(teacher)
    p6 = p5.next_class
    row = {
        "first_name": "Brian",
        "last_name": "Okello",
        "sex": "M",
        "father_name": "Tom Okello",
        "father_phone": "0772555111",
        "allergies": "Peanuts",
    }
    refused = client.post(
        "/api/learners/enrol/",
        {**row, "school_class": p6.id, "academic_year": term.academic_year_id},
        format="json",
    )
    assert refused.status_code == 400
    made = client.post(
        "/api/learners/enrol/",
        {**row, "school_class": p5.id, "academic_year": term.academic_year_id},
        format="json",
    )
    assert made.status_code == 201, made.json()
    learner = Learner.objects.get(pk=made.json()["id"])
    assert learner.adm_no and learner.has_medical_alert
    assert Enrolment.objects.get(learner=learner).term == term
    assert learner.guardian_links.get().relationship == "Father"


def test_director_imports_a_class_from_excel(school, term, p5, director, client_for):
    client = client_for(director)
    upload = _filled_template(client, [{"First name": "Joan", "Surname": "Akello", "Sex (M/F)": "F"}])
    result = client.post(
        "/api/learners/import-excel/",
        {"file": upload, "academic_year": term.academic_year_id, "school_class": p5.id},
        format="multipart",
    ).json()
    assert result["created"] == 1
    assert Learner.objects.get(first_name="Joan").adm_no
