"""Performance history across terms, and every module having someone who can act in it."""

import datetime

import pytest
from django.urls import get_resolver

from apps.accounts.roles import PLATFORM_ONLY, ROLE_PERMS
from apps.assessment.reports import generate_report_cards
from apps.schoolsetup.models import Term

from .factories import enrol, make_user
from .helpers import approve_all_offered, exam

pytestmark = pytest.mark.django_db


def _views():
    found = {}

    def walk(patterns):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                walk(p.url_patterns)
                continue
            cls = getattr(p.callback, "cls", None) or getattr(p.callback, "view_class", None)
            if cls is not None:
                found[cls.__name__] = cls

    walk(get_resolver().url_patterns)
    return found.values()


def test_every_module_action_has_a_top_school_role():
    """Once the owner console switches a module on, the director or head teacher can use it
    even before specialist accounts (bursar, librarian, nurse) exist."""
    top = ROLE_PERMS["director"] | ROLE_PERMS["head_teacher"]
    # Entering marks is each teacher's own job (their allocated subjects or class).
    teacher_only = {"marks.enter"}
    missing = []
    for view in _views():
        if not getattr(view, "module", None):
            continue
        perms = {getattr(view, "perms", {}).get("write"), *getattr(view, "action_perms", {}).values()}
        for perm in perms - {None, PLATFORM_ONLY} - teacher_only:
            if perm not in top:
                missing.append(f"{view.__name__}: {perm}")
    assert not missing, missing


def test_director_can_act_in_operational_modules(school, director, client_for):
    from apps.subscriptions.services import set_module

    set_module(school, "library", True)
    client = client_for(director)
    assert (
        client.post(
            "/api/staff/", {"first_name": "Ruth", "last_name": "Akello", "kind": "teaching"}, format="json"
        ).status_code
        == 201
    )
    assert client.post("/api/library/books/", {"title": "Primary Maths 5"}, format="json").status_code == 201
    assert (
        client.post("/api/finance/suppliers/", {"name": "Kampala Stationers"}, format="json").status_code
        == 201
    )


@pytest.fixture
def two_terms(school, term, p5, learners):
    """Term 1 (results never computed) and Term 2 (report cards generated)."""
    earlier = Term.objects.create(
        school=school,
        academic_year=term.academic_year,
        number=2,
        start_date=term.start_date - datetime.timedelta(days=140),
        end_date=term.start_date - datetime.timedelta(days=60),
        status="closed",
    )
    for learner in learners:
        enrol(learner, earlier, p5)
    approve_all_offered(exam(earlier, p5), p5, learners, lambda l, s: 40 + learners.index(l) * 10)
    approve_all_offered(exam(term, p5), p5, learners, lambda l, s: 50 + learners.index(l) * 10)
    generate_report_cards(term, p5)
    return earlier, term


def test_class_history_fills_in_past_terms(school, p5, two_terms, dos, client_for):
    earlier, current = two_terms
    data = client_for(dos).get("/api/analytics/history/", {"school_class": p5.id}).json()
    assert [t["term"] for t in data["terms"]] == [earlier.id, current.id]
    first, second = data["terms"]
    assert first["average"] == 55.0 and second["average"] == 65.0
    assert first["pass_rate"] == 75.0 and second["pass_rate"] == 100.0
    assert first["subjects"] and set(data["subjects"]) == set(second["subjects"])

    school_view = client_for(dos).get("/api/analytics/history/").json()
    assert len(school_view["terms"]) == 2
    row = next(c for c in school_view["classes"] if c["id"] == p5.id)
    assert row["terms"][str(current.id)] == 65.0


def test_learner_history_lists_terms_and_report_cards(school, p5, learners, two_terms, client_for):
    teacher = make_user(school, ("class_teacher", "class", p5.id))
    data = client_for(teacher).get(f"/api/analytics/history/learner/{learners[3].id}/").json()
    assert [t["average"] for t in data["terms"]] == [70.0, 80.0]
    assert data["terms"][0]["report_card"] is None and data["terms"][1]["report_card"]["id"]
    other_teacher = make_user(school, ("class_teacher", "class", p5.next_class_id))
    assert (
        client_for(other_teacher).get(f"/api/analytics/history/learner/{learners[3].id}/").status_code == 400
    )
