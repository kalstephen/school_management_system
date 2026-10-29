import datetime

import pytest

from apps.assessment.grading import compute_class_results
from apps.assessment.models import ReportCard
from apps.assessment.reports import generate_report_cards
from apps.learners.models import Enrolment
from apps.promotion.models import PromotionRule
from apps.schoolsetup.models import AcademicYear, Term

from .factories import LearnerFactory, enrol
from .helpers import approve_all_offered, exam

pytestmark = pytest.mark.django_db


@pytest.fixture
def next_term(school, today):
    year = AcademicYear.objects.create(
        school=school,
        name=str(today.year + 1),
        start_date=today + datetime.timedelta(days=100),
        end_date=today + datetime.timedelta(days=400),
    )
    return Term.objects.create(
        school=school,
        academic_year=year,
        number=1,
        start_date=today + datetime.timedelta(days=100),
        end_date=today + datetime.timedelta(days=190),
    )


def test_promotion_review_chain(school, term, p5, next_term, head, dos, director, client_for):
    """Class teacher reviews, DOS recommends, director approves; the DOS and the director can
    change any decision on the way."""
    from .factories import make_user

    strong, borderline, weak, missing = (LearnerFactory(school=school) for _ in range(4))
    for learner in (strong, borderline, weak, missing):
        enrol(learner, term, p5)
    PromotionRule.objects.create(
        school=school, school_class=p5, measure="term3_average", pass_mark=50, probation_mark=45
    )
    eot = exam(term, p5)
    scores = {strong: 80, borderline: 47, weak: 30}
    approve_all_offered(eot, p5, [strong, borderline, weak], lambda l, s: scores[l])
    compute_class_results(term, p5)
    generate_report_cards(term, p5, allow_unapproved=True)
    teacher = make_user(school, ("class_teacher", "class", p5.id))
    p6_teacher = make_user(school, ("class_teacher", "class", p5.next_class_id))

    # The class teacher prepares the list for their own class only.
    teacher_client = client_for(teacher)
    assert (
        client_for(p6_teacher)
        .post("/api/promotion-batches/", {"term": term.id, "school_class": p5.id}, format="json")
        .status_code
        == 400
    )
    batch = teacher_client.post(
        "/api/promotion-batches/", {"term": term.id, "school_class": p5.id}, format="json"
    ).json()
    assert batch["status"] == "proposed" and batch["pass_mark"] == "50.00"
    url = f"/api/promotion-batches/{batch['id']}"
    decisions = {d["learner"]: d for d in teacher_client.get(f"{url}/decisions/").json()}
    assert decisions[strong.id]["final"] == "promote" and decisions[strong.id]["to_class_name"] == "P6"
    assert decisions[borderline.id]["final"] == "probation"
    assert decisions[weak.id]["final"] == "repeat" and decisions[weak.id]["to_class_name"] == "P5"
    assert decisions[missing.id]["final"] == "review"
    assert not client_for(p6_teacher).get("/api/promotion-batches/").json()["results"]

    # The class teacher comments but cannot change decisions, then sends it to the DOS.
    assert (
        teacher_client.post(
            f"{url}/comment/", {"decision": decisions[weak.id]["id"], "comment": "Often sick"}, format="json"
        ).json()["teacher_comment"]
        == "Often sick"
    )
    assert (
        teacher_client.post(
            f"{url}/override/", {"decision": decisions[weak.id]["id"], "final": "promote", "reason": "x"}
        ).status_code
        == 403
    )
    assert teacher_client.post(f"{url}/submit/", {"note": "Checked"}).json()["status"] == "submitted"

    # The DOS must settle missing marks before recommending, and cannot approve.
    dos_client = client_for(dos)
    assert dos_client.post(f"{url}/recommend/").status_code == 400
    assert (
        dos_client.post(
            f"{url}/override/", {"decision": decisions[missing.id]["id"], "final": "promote"}, format="json"
        ).status_code
        == 400
    )  # a reason is required
    dos_client.post(
        f"{url}/override/",
        {"decision": decisions[missing.id]["id"], "final": "promote", "reason": "Sat exams late; passed"},
        format="json",
    )
    assert dos_client.post(f"{url}/approve/").status_code == 403
    assert dos_client.post(f"{url}/recommend/", {"note": "Agreed"}).json()["status"] == "recommended"
    assert (
        dos_client.post(
            f"{url}/override/", {"decision": decisions[weak.id]["id"], "final": "promote", "reason": "x"}
        ).status_code
        == 400
    )  # with the director now

    # The director passes the weak learner anyway and approves.
    director_client = client_for(director)
    director_client.post(
        f"{url}/override/",
        {"decision": decisions[weak.id]["id"], "final": "probation", "reason": "Improved in Term 3"},
        format="json",
    )
    approved = director_client.post(f"{url}/approve/", {"note": "Approved"}).json()
    assert approved["status"] == "approved" and approved["approved_by_name"]
    assert ReportCard.objects.get(learner=strong, term=term).promotion_note == "Promoted to P6"
    assert ReportCard.objects.get(learner=weak, term=term).promotion_note == "Promoted to P6 on probation"

    applied = director_client.post(f"{url}/apply/", {"target_term": next_term.id}, format="json").json()
    assert applied["status"] == "applied"
    assert Enrolment.objects.get(learner=strong, term=next_term).school_class.name == "P6"
    assert Enrolment.objects.get(learner=weak, term=next_term).school_class.name == "P6"
    assert director_client.post(f"{url}/undo/").json()["status"] == "undone"
    assert not Enrolment.objects.filter(term=next_term).exists()


def test_demote_and_send_back(school, term, p5, learners, dos, client_for):
    client = client_for(dos)
    batch = client.post(
        "/api/promotion-batches/", {"term": term.id, "school_class": p5.id, "pass_mark": 40}, format="json"
    ).json()
    assert batch["pass_mark"] == "40.00" and batch["measure_label"] == "Term average (%)"
    url = f"/api/promotion-batches/{batch['id']}"
    decision = client.get(f"{url}/decisions/").json()[0]
    demoted = client.post(
        f"{url}/override/", {"decision": decision["id"], "final": "demote", "reason": "Cannot read yet"}
    ).json()
    assert demoted["final"] == "demote" and demoted["to_class_name"] == "P4"
    client.post(f"{url}/submit/")
    assert client.post(f"{url}/send-back/", {"note": "Recheck marks"}).json()["status"] == "proposed"


def test_candidate_class_completes(school, term, p7, next_term, head, client_for):
    learner = LearnerFactory(school=school)
    enrol(learner, term, p7)
    client = client_for(head)
    batch = client.post(
        "/api/promotion-batches/", {"term": term.id, "school_class": p7.id}, format="json"
    ).json()
    assert batch["counts"] == {"complete": 1}
    client.post(f"/api/promotion-batches/{batch['id']}/recommend/")
    client.post(f"/api/promotion-batches/{batch['id']}/approve/")
    client.post(f"/api/promotion-batches/{batch['id']}/apply/", {"target_term": next_term.id}, format="json")
    learner.refresh_from_db()
    assert learner.status == "completed"


def test_promotion_without_a_rule_uses_the_average(school, term, p5, learners, dos, client_for):
    response = client_for(dos).post(
        "/api/promotion-batches/", {"term": term.id, "school_class": p5.id}, format="json"
    )
    assert response.status_code == 201 and response.json()["pass_mark"] == "50.00"


def test_ple_aggregate_rule_lower_is_better(school):
    from apps.promotion.services import decide

    rule = PromotionRule(measure="ple_aggregate", pass_mark=24, probation_mark=28)
    assert decide(rule, 12) == "promote" and decide(rule, 26) == "probation" and decide(rule, 33) == "repeat"
    assert decide(rule, None) == "review"
