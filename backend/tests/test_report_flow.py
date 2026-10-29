"""The report card path end to end, through the API: the class teacher enters marks for
every subject of their class, the DOS approves them, the class teacher prepares, comments
on and prints the report cards, and the head teacher publishes them."""

import pytest

from apps.assessment.models import ReportCard

from .factories import make_user
from .helpers import exam

pytestmark = pytest.mark.django_db


def test_class_teacher_marks_to_published_report(school, term, p5, p7, learners, dos, head, client_for):
    teacher = make_user(school, ("class_teacher", "class", p5.id))  # no subject allocations
    ct, dos_client, head_client = client_for(teacher), client_for(dos), client_for(head)
    eot = exam(term, p5)
    assert dos_client.post(f"/api/exams/{eot.id}/prepare-sheets/", {}, format="json").json()["created"] > 0

    # 1. The class teacher sees every sheet of their class as theirs, enters marks, submits.
    sheets = ct.get("/api/mark-sheets/", {"exam": eot.id, "mine": 1, "page_size": 100}).json()["results"]
    assert sheets and all(s["school_class"] == p5.id for s in sheets)
    for sheet in sheets:
        entries = ct.get(f"/api/mark-sheets/{sheet['id']}/entries/").json()
        assert entries["editable"] is True
        marks = [
            {"learner": row["learner"], "score": 40 + 10 * i} for i, row in enumerate(entries["learners"])
        ]
        saved = ct.post(f"/api/mark-sheets/{sheet['id']}/entries/", {"marks": marks}, format="json")
        assert saved.status_code == 200, saved.json()
        assert ct.post(f"/api/mark-sheets/{sheet['id']}/submit/").json()["status"] == "submitted"
        # The class teacher cannot approve their own marks.
        assert ct.post(f"/api/mark-sheets/{sheet['id']}/approve/").status_code == 403

    # Report cards wait for approval.
    pending = ct.post("/api/report-cards/generate/", {"term": term.id, "school_class": p5.id}, format="json")
    assert pending.status_code == 400 and pending.json()["pending"]

    # 2. The DOS approves and locks the marks.
    approved = dos_client.post(
        "/api/mark-sheets/bulk-approve/", {"ids": [s["id"] for s in sheets]}, format="json"
    ).json()
    assert approved["approved"] == len(sheets)
    locked = ct.post(
        f"/api/mark-sheets/{sheets[0]['id']}/entries/",
        {"marks": [{"learner": learners[0].id, "score": 1}]},
        format="json",
    )
    assert locked.status_code == 400

    # 3. The class teacher prepares the cards, comments and prints — for their own class only.
    made = ct.post("/api/report-cards/generate/", {"term": term.id, "school_class": p5.id}, format="json")
    assert made.json()["generated"] == len(learners)
    assert (
        ct.post(
            "/api/report-cards/generate/", {"term": term.id, "school_class": p7.id}, format="json"
        ).status_code
        == 400
    )
    cards = ct.get("/api/report-cards/", {"term": term.id, "result__school_class": p5.id}).json()["results"]
    assert len(cards) == len(learners)
    commented = ct.patch(
        f"/api/report-cards/{cards[0]['id']}/", {"class_teacher_comment": "Well done."}, format="json"
    )
    assert commented.status_code == 200
    assert (
        ct.patch(f"/api/report-cards/{cards[0]['id']}/", {"head_comment": "x"}, format="json").status_code
        == 400
    )
    pdf = ct.get("/api/report-cards/class-pdf/", {"term": term.id, "school_class": p5.id})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert ct.get("/api/report-cards/class-pdf/", {"term": term.id, "school_class": p7.id}).status_code == 400
    assert (
        ct.post(
            "/api/report-cards/publish/", {"term": term.id, "school_class": p5.id}, format="json"
        ).status_code
        == 403
    )

    # 4. The head teacher comments and publishes.
    head_client.patch(f"/api/report-cards/{cards[0]['id']}/", {"head_comment": "Keep it up."}, format="json")
    published = head_client.post(
        "/api/report-cards/publish/", {"term": term.id, "school_class": p5.id}, format="json"
    )
    assert published.json()["published"] == len(learners)
    card = ReportCard.objects.get(pk=cards[0]["id"])
    assert card.status == "published"
    assert (
        card.snapshot["class_teacher_comment"] == "Well done."
        and card.snapshot["head_comment"] == "Keep it up."
    )
    assert all(row["score"] is not None for row in card.snapshot["subjects"])
