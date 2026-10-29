"""Class teachers and deputies (per class or stream), subject specialisations and subjects
proposed by the school."""

import pytest

from apps.accounts.models import RoleAssignment
from apps.assessment.grading import subjects_offered
from apps.curriculum.models import Subject, SubjectAllocation
from apps.schoolsetup.models import Stream

from .factories import StaffFactory, make_user

pytestmark = pytest.mark.django_db


def _teacher(school):
    user = make_user(school, "subject_teacher")
    return StaffFactory(school=school, user=user, kind="teaching"), user


def _access(user, scope_type, scope_id):
    return RoleAssignment.objects.filter(
        membership__user=user, role="class_teacher", scope_type=scope_type, scope_id=scope_id
    ).exists()


def test_one_class_teacher_and_one_deputy_per_stream(school, p5, dos, client_for):
    east = Stream.objects.create(school=school, school_class=p5, name="East")
    (agnes, agnes_user), (brian, brian_user), (carol, carol_user) = (_teacher(school) for _ in range(3))
    client = client_for(dos)
    post = lambda staff, kind="class_teacher": client.post(  # noqa: E731
        "/api/class-teachers/",
        {"target": f"stream:{east.id}", "post": kind, "staff": staff and staff.id},
        format="json",
    )
    assert post(agnes).status_code == 200 and post(brian, "deputy").status_code == 200
    east.refresh_from_db()
    assert (east.class_teacher, east.deputy_class_teacher) == (agnes, brian)
    assert _access(agnes_user, "stream", east.id) and _access(brian_user, "stream", east.id)

    # Switching: Carol replaces Agnes, who loses the access.
    post(carol)
    east.refresh_from_db()
    assert east.class_teacher == carol
    assert not _access(agnes_user, "stream", east.id) and _access(carol_user, "stream", east.id)

    # The deputy becoming class teacher leaves the deputy post empty, never the same person twice.
    post(brian)
    east.refresh_from_db()
    assert east.class_teacher == brian and east.deputy_class_teacher is None

    # A teacher leads one class at a time: appointing Brian to P5 itself moves him.
    client.post(
        "/api/class-teachers/",
        {"target": f"class:{p5.id}", "post": "class_teacher", "staff": brian.id},
        format="json",
    )
    east.refresh_from_db()
    p5.refresh_from_db()
    assert p5.class_teacher == brian and east.class_teacher is None


def test_only_the_dos_head_director_or_admin_appoint_and_never_themselves(school, p5, dos, client_for):
    teacher, teacher_user = _teacher(school)
    body = {"target": f"class:{p5.id}", "post": "class_teacher", "staff": teacher.id}
    assert client_for(teacher_user).post("/api/class-teachers/", body, format="json").status_code == 403
    dos_staff = StaffFactory(school=school, user=dos, kind="teaching")
    self_appoint = client_for(dos).post(
        "/api/class-teachers/", {**body, "staff": dos_staff.id}, format="json"
    )
    assert self_appoint.status_code == 400 and "yourself" in str(self_appoint.json())


def test_staff_form_sets_class_teacher_posts(school, p5, director, client_for):
    p6 = p5.next_class
    client = client_for(director)
    made = client.post(
        "/api/staff/",
        {
            "first_name": "Ruth",
            "last_name": "Akello",
            "kind": "teaching",
            "class_teacher_of": f"class:{p5.id}",
            "deputy_class_teacher_of": f"class:{p6.id}",
        },
        format="json",
    ).json()
    assert {(p["post"], p["label"]) for p in made["class_posts"]} == {
        ("class_teacher", "P5"),
        ("deputy", "P6"),
    }
    cleared = client.patch(f"/api/staff/{made['id']}/", {"deputy_class_teacher_of": ""}, format="json").json()
    assert [p["post"] for p in cleared["class_posts"]] == ["class_teacher"]


def test_subjects_proposed_wait_for_approval(school, p5, dos, head, client_for):
    hod = make_user(school, "hod")
    proposed = (
        client_for(hod)
        .post(
            "/api/subjects/",
            {"name": "Kiswahili", "level": "primary", "proposal_note": "Required by MoES"},
            format="json",
        )
        .json()
    )
    assert proposed["status"] == "pending"
    subject = Subject.objects.get(pk=proposed["id"])
    assert subject not in subjects_offered(p5)
    assert proposed["id"] not in [
        s["id"] for s in client_for(dos).get("/api/subjects/", {"page_size": 200}).json()["results"]
    ]
    assert (
        client_for(hod).post(f"/api/subjects/{subject.id}/decide/", {"decision": "approve"}).status_code
        == 403
    )

    # The DOS may propose too, but someone else approves.
    own = (
        client_for(dos).post("/api/subjects/", {"name": "Chinese", "level": "primary"}, format="json").json()
    )
    assert (
        client_for(dos).post(f"/api/subjects/{own['id']}/decide/", {"decision": "approve"}).status_code == 400
    )

    approved = client_for(head).post(f"/api/subjects/{subject.id}/decide/", {"decision": "approve"}).json()
    assert approved["status"] == "approved" and approved["decided_by_name"]
    assert subject in subjects_offered(p5)


def test_specialisations_fill_who_teaches_what(school, p5, dos, client_for):
    maths = Subject.objects.get(school=school, level="primary", name="Mathematics")
    english = Subject.objects.get(school=school, level="primary", name="English")
    a, _ = _teacher(school)
    b, _ = _teacher(school)
    client = client_for(dos)
    assert (
        client.post(
            f"/api/staff/{a.id}/specialisations/", {"subjects": [maths.id, english.id]}, format="json"
        ).status_code
        == 200
    )
    client.post(f"/api/staff/{b.id}/specialisations/", {"subjects": [maths.id]}, format="json")
    result = client.post("/api/allocations/from-specialisations/", {"classes": [p5.id]}, format="json").json()
    allocations = SubjectAllocation.objects.filter(school_class=p5)
    assert allocations.get(subject=maths).teacher in (a, b) and allocations.get(subject=english).teacher == a
    assert result["unfilled"] and all("P5" in row for row in result["unfilled"])
    again = client.post("/api/allocations/from-specialisations/", {"classes": [p5.id]}, format="json").json()
    assert again["created"] == []

    pending = Subject.objects.create(school=school, name="Robotics", level="primary", status="pending")
    refused = client.post(f"/api/staff/{a.id}/specialisations/", {"subjects": [pending.id]}, format="json")
    assert refused.status_code == 400


def test_subject_comments_and_initials_on_report_cards(school, term, p5, learners, client_for):
    from apps.assessment.models import ReportCard
    from apps.assessment.reports import generate_report_cards

    from .helpers import approve_all_offered, exam

    teacher_staff, teacher_user = _teacher(school)
    teacher_staff.first_name, teacher_staff.last_name = "Agnes", "Nakimuli"
    teacher_staff.save()
    p5.class_teacher = teacher_staff
    p5.save()
    from apps.schoolsetup.class_teachers import sync_access

    sync_access(p5)
    approve_all_offered(exam(term, p5), p5, learners, lambda l, s: 55 + learners.index(l) * 10)
    maths = Subject.objects.get(school=school, level="primary", name="Mathematics")
    client = client_for(teacher_user)
    query = {"term": term.id, "school_class": p5.id, "subject": maths.id}
    sheet = client.get("/api/subject-comments/", query).json()
    assert sheet["editable"] and sheet["learners"][0]["suggested"]
    best = max(sheet["learners"], key=lambda r: r["score"])
    assert best["suggested"] == "Excellent. Keep it up."
    saved = client.post(
        "/api/subject-comments/",
        {**query, "comments": [{"learner": best["learner"], "text": "Brilliant at fractions."}]},
        format="json",
    )
    assert saved.json()["saved"] == 1

    generate_report_cards(term, p5)
    card = ReportCard.objects.get(learner_id=best["learner"], term=term)
    rows = {r["name"]: r for r in card.snapshot["subjects"]}
    assert rows["Mathematics"]["comment"] == "Brilliant at fractions."
    assert rows["English"]["comment"] == "Excellent. Keep it up."
    assert rows["Mathematics"]["initials"] == "AN"

    other_staff, other_user = _teacher(school)
    refused = client_for(other_user).post(
        "/api/subject-comments/",
        {**query, "comments": [{"learner": best["learner"], "text": "x"}]},
        format="json",
    )
    assert refused.status_code == 400
