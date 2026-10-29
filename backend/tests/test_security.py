"""School isolation, roles, module switches, subscriptions, audit log and login."""

import datetime

import pytest
from django.utils import timezone

from apps.core.models import AccessLog, AuditLog
from apps.learners.models import Learner
from apps.schoolsetup.models import SchoolClass
from apps.subscriptions.models import Plan, Subscription, SupportAccessGrant
from apps.subscriptions.services import set_module

from .factories import LearnerFactory, UserFactory, enrol, make_user

pytestmark = pytest.mark.django_db


def test_school_isolation_on_lists_and_details(school, other_school, term, learners, head, client_for):
    outsider = LearnerFactory(school=other_school)
    client = client_for(head)
    ids = [row["id"] for row in client.get("/api/learners/").json()["results"]]
    assert outsider.id not in ids and len(ids) == 4
    assert client.get(f"/api/learners/{outsider.id}/").status_code == 404


def test_cannot_link_to_another_schools_records(school, other_school, term, head, client_for):
    foreign_class = SchoolClass.objects.get(school=other_school, name="P5")
    response = client_for(head).post(
        "/api/enrolments/",
        {
            "learner": LearnerFactory(school=school).id,
            "term": term.id,
            "school_class": foreign_class.id,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "school_class" in response.json()


def test_audit_log_records_before_and_after(school, term, learners, head, client_for):
    learner = learners[0]
    client_for(head).patch(f"/api/learners/{learner.id}/", {"lin": "LIN-777"}, format="json")
    log = AuditLog.objects.filter(
        entity="learners.learner", object_id=str(learner.id), action="update"
    ).first()
    assert log.changes["lin"] == ["", "LIN-777"]
    assert log.user.username == "head"


def test_health_fields_hidden_from_teachers_and_views_logged(
    school, term, p5, learners, nurse, teacher_factory, client_for
):
    from apps.curriculum.models import Subject

    learner = learners[0]
    Learner.objects.filter(pk=learner.pk).update(allergies="Peanuts", has_medical_alert=True)
    teacher = teacher_factory((Subject.objects.get(school=school, level="primary", short_name="ENG"), p5))
    body = client_for(teacher).get(f"/api/learners/{learner.id}/").json()
    assert "allergies" not in body and body["medical_flag"] == "See nurse"
    body = client_for(nurse).get(f"/api/learners/{learner.id}/").json()
    assert body["allergies"] == "Peanuts"
    assert AccessLog.objects.filter(resource="learner.health", object_id=str(learner.id)).exists()


def test_roles_block_what_a_job_does_not_need(school, term, learners, bursar, client_for):
    client = client_for(bursar)
    assert client.get("/api/mark-sheets/").status_code == 403
    assert client.get("/api/learners/").status_code == 403
    assert client.get("/api/finance/expenses/").status_code == 200


def test_subject_teacher_sees_only_their_classes(school, term, p5, learners, teacher_factory, client_for):
    from apps.curriculum.models import Subject

    p6 = SchoolClass.objects.get(school=school, name="P6")
    elsewhere = LearnerFactory(school=school)
    enrol(elsewhere, term, p6)
    teacher = teacher_factory((Subject.objects.get(school=school, level="primary", short_name="MTC"), p5))
    ids = {r["id"] for r in client_for(teacher).get("/api/learners/").json()["results"]}
    assert elsewhere.id not in ids and {l.id for l in learners} <= ids


def test_addon_switches_hide_module_without_losing_data(school, head, client_for):
    client = client_for(head)
    assert client.get("/api/library/books/").status_code == 403
    set_module(school, "library", True)
    assert (
        client.post("/api/library/books/", {"title": "Oxford Primary Atlas"}, format="json").status_code
        == 201
    )
    set_module(school, "library", False)
    assert client.get("/api/library/books/").status_code == 403
    set_module(school, "library", True)
    assert client.get("/api/library/books/").json()["count"] == 1


def test_school_sees_addons_but_cannot_change_them(school, client_for):
    admin = make_user(school, "school_admin")
    client = client_for(admin)
    set_module(school, "sickbay", True)
    assert next(r for r in client.get("/api/addons/").json() if r["module"] == "sickbay")["active"]
    assert (
        client.post("/api/addons/", {"module": "sickbay", "hidden": True}, format="json").status_code == 403
    )


def test_expired_subscription_is_read_only(school, term, learners, head, client_for):
    plan = Plan.objects.create(name="Basic", max_learners=300, price_per_term=99000)
    Subscription.objects.create(
        school=school,
        plan=plan,
        status="active",
        starts_on=datetime.date(2020, 1, 1),
        ends_on=timezone.localdate() - datetime.timedelta(days=1),
    )
    client = client_for(head)
    assert client.get("/api/learners/").status_code == 200
    assert client.get("/api/learners/export/").status_code == 200
    assert client.patch(f"/api/learners/{learners[0].id}/", {"lin": "X"}, format="json").status_code == 403


def test_platform_admin_needs_support_access(school, term, learners, client_for):
    staff = UserFactory(is_platform_admin=True)
    client = client_for(staff)
    assert client.get("/api/learners/", HTTP_X_SCHOOL_ID=str(school.id)).status_code == 403
    assert client.get("/api/platform/schools/").status_code == 200
    SupportAccessGrant.objects.create(
        school=school,
        reason="Help with report cards",
        expires_at=timezone.now() + datetime.timedelta(hours=2),
    )
    assert client.get("/api/learners/", HTTP_X_SCHOOL_ID=str(school.id)).status_code == 200
    assert (
        client.post(
            "/api/learners/", {"first_name": "X"}, HTTP_X_SCHOOL_ID=str(school.id), format="json"
        ).status_code
        == 403
    )


def test_login_me_and_lockout(school, head, client):
    from rest_framework.test import APIClient

    api = APIClient()
    bad = {"school_code": school.code, "username": "head", "password": "wrong"}
    for _ in range(5):
        assert api.post("/api/auth/login/", bad, format="json").status_code == 400
    assert (
        api.post(
            "/api/auth/login/",
            {"school_code": school.code, "username": "head", "password": "Pass-12345"},
            format="json",
        ).status_code
        == 429
    )
    head.refresh_from_db()
    head.locked_until = None
    head.save()
    me = api.post(
        "/api/auth/login/",
        {"school_code": school.code, "username": "HEAD", "password": "Pass-12345"},
        format="json",
    ).json()
    assert me["school"]["id"] == school.id
    assert "marks.approve" in me["perms"] and "finance.approve" in me["perms"]
    assert "library" not in me["modules"] and "finance" in me["modules"]


def test_time_limited_permission_grant(school, term, learners, client_for):
    from apps.accounts.models import PermissionGrant

    librarian = make_user(school, "librarian")
    client = client_for(librarian)
    assert client.get("/api/discipline-cases/").status_code == 403
    PermissionGrant.objects.create(
        school=school,
        membership=librarian.memberships.first(),
        permission="discipline.view",
        reason="Cover",
        expires_at=timezone.now() + datetime.timedelta(days=1),
    )
    assert client.get("/api/discipline-cases/").status_code == 200
