"""Mark entry checks, the approval workflow, report cards (PDF, QR verification,
reissue after reopening) and UNEB import."""

import io

import pytest
from django.core import mail

from apps.assessment.models import MarkSheet, ReportCard
from apps.learners.models import Guardian, LearnerGuardian

from .factories import make_user
from .helpers import approve_all_offered, exam, ple_subjects

pytestmark = pytest.mark.django_db


@pytest.fixture
def maths(school):
    return ple_subjects(school)["MTC"]


@pytest.fixture
def sheet(school, term, p5, learners, maths):
    eot = exam(term, p5)
    return MarkSheet.objects.create(school=school, exam=eot, subject=maths, school_class=p5)


def test_prepare_sheets_creates_one_per_subject(school, term, p5, dos, client_for):
    eot = exam(term, p5)
    created = (
        client_for(dos).post(f"/api/exams/{eot.id}/prepare-sheets/", {}, format="json").json()["created"]
    )
    assert created == 7  # ENG, MTC, SCI, SST, RE, LIT and the local-language elective


def test_mark_entry_validates_and_records_history(
    school, sheet, learners, maths, p5, teacher_factory, client_for
):
    teacher = teacher_factory((maths, p5))
    client = client_for(teacher)
    marks = [
        {"learner": learners[0].id, "score": 67},
        {"learner": learners[1].id, "score": 123},
        {"learner": learners[2].id, "score": "abc"},
        {"learner": learners[3].id, "score": None, "is_absent": True},
    ]
    result = client.post(f"/api/mark-sheets/{sheet.id}/entries/", {"marks": marks}, format="json").json()
    assert result["saved"] == 2
    errors = {e["learner"]: e["error"] for e in result["errors"]}
    assert "out of range" in errors[learners[1].id] and "not a number" in errors[learners[2].id]
    client.post(
        f"/api/mark-sheets/{sheet.id}/entries/",
        {"marks": [{"learner": learners[0].id, "score": 70}]},
        format="json",
    )
    history = client.get(f"/api/mark-sheets/{sheet.id}/history/").json()
    assert any(
        h["changes"].get("score") == ["67.00", "70"]
        or h["changes"].get("score", [None])[0] in ("67.00", "67")
        for h in history
    )


def test_only_allocated_teacher_can_enter_marks(school, sheet, learners, p5, teacher_factory, client_for):
    english = ple_subjects(school)["ENG"]
    stranger = teacher_factory((english, p5))
    response = client_for(stranger).post(
        f"/api/mark-sheets/{sheet.id}/entries/",
        {"marks": [{"learner": learners[0].id, "score": 50}]},
        format="json",
    )
    assert response.status_code == 400 and "not allocated" in response.json()["detail"]


def test_full_approval_workflow_and_locking(
    school, sheet, learners, maths, p5, dos, teacher_factory, client_for
):
    from apps.schoolsetup.models import Department

    department = Department.objects.get(school=school, name="Mathematics")
    maths.department = department
    maths.save()
    teacher = teacher_factory((maths, p5))
    hod = make_user(school, ("hod", "department", department.id))
    client = client_for(teacher)
    client.post(
        f"/api/mark-sheets/{sheet.id}/entries/",
        {"marks": [{"learner": learners[0].id, "score": 50}]},
        format="json",
    )
    missing = client.post(f"/api/mark-sheets/{sheet.id}/submit/")
    assert missing.status_code == 400 and len(missing.json()["missing"]) == 3
    client.post(
        f"/api/mark-sheets/{sheet.id}/entries/",
        {"marks": [{"learner": l.id, "score": 60} for l in learners[1:]]},
        format="json",
    )
    assert client.post(f"/api/mark-sheets/{sheet.id}/submit/").json()["status"] == "submitted"
    assert client.post(f"/api/mark-sheets/{sheet.id}/approve/").status_code == 403  # teacher cannot approve
    assert client_for(hod).post(f"/api/mark-sheets/{sheet.id}/review/").json()["status"] == "reviewed"
    assert client_for(dos).post(f"/api/mark-sheets/{sheet.id}/approve/").json()["status"] == "approved"
    locked = client.post(
        f"/api/mark-sheets/{sheet.id}/entries/",
        {"marks": [{"learner": learners[0].id, "score": 99}]},
        format="json",
    )
    assert locked.status_code == 400 and "cannot be edited" in locked.json()["detail"]
    assert client_for(dos).post(f"/api/mark-sheets/{sheet.id}/reopen/", {}, format="json").status_code == 400
    reopened = (
        client_for(dos)
        .post(f"/api/mark-sheets/{sheet.id}/reopen/", {"reason": "Wrong script total"}, format="json")
        .json()
    )
    assert reopened["status"] == "returned" and reopened["reopen_reason"] == "Wrong script total"


def test_report_cards_generate_publish_pdf_and_verify(school, term, p5, learners, head, client_for):
    eot = exam(term, p5)
    client = client_for(head)
    approve_all_offered(eot, p5, learners[:3], lambda l, s: 70)
    sheet = MarkSheet.objects.filter(exam=eot).first()
    sheet.status = "draft"
    sheet.save()
    blocked = client.post(
        "/api/report-cards/generate/", {"term": term.id, "school_class": p5.id}, format="json"
    )
    assert blocked.status_code == 400 and blocked.json()["pending"]
    sheet.status = "approved"
    sheet.save()
    assert (
        client.post(
            "/api/report-cards/generate/", {"term": term.id, "school_class": p5.id}, format="json"
        ).json()["generated"]
        == 4
    )
    card = ReportCard.objects.filter(learner=learners[0]).first()
    assert card.class_teacher_comment  # suggested from the comment bank
    assert (
        client.patch(
            f"/api/report-cards/{card.id}/", {"head_comment": "Well done"}, format="json"
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/report-cards/publish/", {"term": term.id, "school_class": p5.id}, format="json"
        ).json()["published"]
        == 4
    )
    pdf = client.get(f"/api/report-cards/{card.id}/pdf/")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert (
        client.get(f"/api/report-cards/class-pdf/?term={term.id}&school_class={p5.id}").content[:4] == b"%PDF"
    )
    card.refresh_from_db()
    public = client.__class__().get(f"/api/public/verify/{card.verify_token}/").json()
    assert public["valid"] is True and public["serial"] == card.serial and "average" not in public
    assert (
        client.patch(f"/api/report-cards/{card.id}/", {"head_comment": "x"}, format="json").status_code == 400
    )


def test_changed_results_reissue_card_under_new_serial(school, term, p5, learners, head, client_for):
    from apps.assessment.models import Mark

    eot = exam(term, p5)
    base = {
        learner.id: 60 + 5 * index for index, learner in enumerate(learners)
    }  # learners[3] tops the class
    approve_all_offered(eot, p5, learners, lambda l, s: base[l.id])
    client = client_for(head)
    body = {"term": term.id, "school_class": p5.id}
    client.post("/api/report-cards/generate/", body, format="json")
    client.post("/api/report-cards/publish/", body, format="json")
    top = learners[3]
    old = ReportCard.objects.get(learner=top)
    Mark.objects.filter(learner=top, mark_sheet__subject__short_name="MTC").update(score=95)
    client.post("/api/report-cards/generate/", body, format="json")
    client.post("/api/report-cards/publish/", body, format="json")
    old.refresh_from_db()
    new = ReportCard.objects.get(learner=top, status="published")
    assert old.status == "superseded" and old.superseded_by == new and new.serial != old.serial
    assert client.__class__().get(f"/api/public/verify/{old.verify_token}/").json()["valid"] is False
    assert ReportCard.objects.filter(learner=learners[1]).count() == 1  # unchanged results keep their card


def test_email_report_cards_to_guardians(school, term, p5, learners, head, client_for):
    eot = exam(term, p5)
    approve_all_offered(eot, p5, learners, lambda l, s: 65)
    guardian = Guardian.objects.create(school=school, full_name="Mary N.", email="mary@example.com")
    LearnerGuardian.objects.create(school=school, learner=learners[0], guardian=guardian)
    client = client_for(head)
    body = {"term": term.id, "school_class": p5.id}
    client.post("/api/report-cards/generate/", body, format="json")
    client.post("/api/report-cards/publish/", body, format="json")
    result = client.post("/api/report-cards/email/", body, format="json").json()
    assert result == {"sent": 1, "failed": 0, "no_email": 3}
    assert mail.outbox[0].attachments[0][2] == "application/pdf"


def test_uneb_import_and_analysis(school, learners, dos, client_for):
    learner = learners[0]
    csv_text = (
        "index_number,candidate_name,sex,aggregate,division,ENG,MTC,SCI,SST\n"
        f"001,{learner.full_name},{learner.sex},8,1,D1,D2,C3,D2\n"
        "002,Someone Else,F,30,4,C6,P7,P8,C5\n"
        "003,,M,10,1,D1,D1,D1,D1\n"
    )
    upload = io.BytesIO(csv_text.encode())
    upload.name = "ple.csv"
    client = client_for(dos)
    result = client.post(
        "/api/uneb-results/import/", {"file": upload, "year": 2026, "level": "PLE"}, format="multipart"
    ).json()
    assert result["created"] == 2 and result["errors"][0]["row"] == 4
    analysis = client.get("/api/uneb-results/analysis/?level=PLE").json()
    assert analysis["years"][0]["candidates"] == 2 and analysis["years"][0]["divisions"] == {"1": 1, "4": 1}
    assert {s["code"] for s in analysis["subjects"]} == {"ENG", "MTC", "SCI", "SST"}
