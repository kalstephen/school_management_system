"""Grading engines: PLE (first), generic, CBC and UACE."""

import pytest

from apps.assessment.grading import compute_class_results, ple_division
from apps.assessment.models import AOIScore
from apps.curriculum.models import Competency, Subject
from apps.learners.models import SubjectEnrolment
from apps.schoolsetup.models import SchoolClass

from .factories import LearnerFactory, enrol
from .helpers import approve_all_offered, approved_marks, exam, ple_subjects

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "aggregate,division",
    [(4, "I"), (12, "I"), (13, "II"), (23, "II"), (24, "III"), (30, "IV"), (35, "U"), (36, "U")],
)
def test_ple_divisions(aggregate, division):
    assert ple_division(aggregate) == division


def test_ple_aggregate_division_and_positions(school, term, p7):
    a, b, c = (LearnerFactory(school=school) for _ in range(3))
    for learner in (a, b, c):
        enrol(learner, term, p7)
    eot = exam(term, p7)
    scores = {a: 95, b: 72, c: 72}
    approve_all_offered(eot, p7, [a, b, c], lambda l, s: scores[l] if s.in_aggregate else 60)
    results = {r.learner_id: r for r in compute_class_results(term, p7)}
    assert results[a.id].aggregate == 4 and results[a.id].division == "I"  # D1 ×4
    assert results[b.id].aggregate == 12 and results[b.id].division == "I"  # C3 ×4
    subjects = {row["short_name"]: row for row in results[a.id].subjects}
    assert subjects["ENG"]["grade"] == "D1" and subjects["RE"]["grade"] == "C4"
    assert results[a.id].position == 1
    assert results[b.id].position == results[c.id].position == 2  # ties share a position
    assert results[a.id].out_of == 3


def test_missing_aggregate_subject_makes_result_incomplete(school, term, p7):
    learner = LearnerFactory(school=school)
    enrol(learner, term, p7)
    eot = exam(term, p7)
    subjects = ple_subjects(school)
    for code in ("ENG", "MTC", "SCI"):
        approved_marks(eot, p7, subjects[code], {learner: 70})
    result = compute_class_results(term, p7)[0]
    assert result.aggregate is None and result.division == "" and result.is_complete is False


def test_term_score_weights_exams_and_ignores_unapproved_marks(school, term, p7):
    learner = LearnerFactory(school=school)
    enrol(learner, term, p7)
    subjects = ple_subjects(school)
    bot, eot = exam(term, p7, "bot", weight=30), exam(term, p7, "eot", weight=70)
    approved_marks(bot, p7, subjects["ENG"], {learner: 50})
    approved_marks(eot, p7, subjects["ENG"], {learner: 90})
    sheet = approved_marks(eot, p7, subjects["MTC"], {learner: 10})
    sheet.status = "draft"
    sheet.save()
    row = {r["short_name"]: r for r in compute_class_results(term, p7)[0].subjects}
    assert row["ENG"]["score"] == 78.0  # 0.3×50 + 0.7×90
    assert row["MTC"]["score"] is None  # draft sheet not counted


def test_generic_rule_for_lower_primary(school, term):
    p2 = SchoolClass.objects.get(school=school, name="P2")
    assert p2.section.grading_rule_set == "generic"
    learner = LearnerFactory(school=school)
    enrol(learner, term, p2)
    eot = exam(term, p2)
    approve_all_offered(eot, p2, [learner], lambda l, s: 80)
    result = compute_class_results(term, p2)[0]
    assert float(result.average) == 80.0 and result.aggregate is None and result.position == 1


def test_cbc_adds_school_based_assessment_from_aois(school, term):
    s2 = SchoolClass.objects.get(school=school, name="S2")
    learner = LearnerFactory(school=school)
    enrol(learner, term, s2)
    eot = exam(term, s2)
    approve_all_offered(eot, s2, [learner], lambda l, s: 50)
    physics = Subject.objects.get(school=school, level="olevel", short_name="PHY")
    competency = Competency.objects.create(school=school, subject=physics, topic="Energy")
    AOIScore.objects.create(school=school, learner=learner, competency=competency, term=term, score=3)
    result = compute_class_results(term, s2)[0]
    rows = {r["short_name"]: r for r in result.subjects}
    assert rows["PHY"]["score"] == 60.0  # 3/3×20 + 50×0.8
    assert rows["PHY"]["grade"] == "C"
    assert rows["ENG"]["score"] == 50.0
    assert "LIT" not in rows  # electives only when chosen
    assert s2.section.show_positions is False


def test_uace_points_with_subsidiaries(school, term):
    s6 = SchoolClass.objects.get(school=school, name="S6")
    learner = LearnerFactory(school=school)
    enrol(learner, term, s6)
    subjects = {s.short_name: s for s in Subject.objects.filter(school=school, level="alevel")}
    for code in ("PHY", "CHEM", "MTC", "GP", "SICT"):
        SubjectEnrolment.objects.create(
            school=school, learner=learner, subject=subjects[code], academic_year=term.academic_year
        )
    eot = exam(term, s6)
    for code, score in {"PHY": 85, "CHEM": 72, "MTC": 55, "GP": 60, "SICT": 40}.items():
        approved_marks(eot, s6, subjects[code], {learner: score})
    result = compute_class_results(term, s6)[0]
    grades = {r["short_name"]: (r["grade"], r["points"]) for r in result.subjects}
    assert grades["PHY"] == ("A", 6.0) and grades["CHEM"] == ("B", 5.0) and grades["MTC"] == ("D", 3.0)
    assert grades["GP"] == ("Pass", 1.0) and grades["SICT"] == ("Fail", 0.0)
    assert float(result.points) == 15.0
