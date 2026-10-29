"""The access ladder: general staff → teachers → … → director → platform team → super admin,
and the rules that stop anyone raising their own level."""

import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import Membership, RoleAssignment
from apps.core.models import School

from .factories import UserFactory, make_user

pytestmark = pytest.mark.django_db


def test_staff_member_without_a_role_gets_the_baseline(school, client_for):
    user = UserFactory()
    Membership.objects.create(school=school, user=user)
    client = client_for(user)
    me = client.get("/api/auth/me/").json()
    # Every staff member may also raise a requisition (it then goes up for approval).
    assert set(me["perms"]) == {"dashboard.view", "communication.view", "timetable.view", "finance.request"}
    assert me["rank"] == 0
    assert client.get("/api/dashboard/").status_code == 200
    assert client.get("/api/notices/").status_code == 200
    assert client.get("/api/learners/").status_code == 403


def test_disabled_account_loses_even_the_baseline(school, client_for):
    user = UserFactory()
    Membership.objects.create(school=school, user=user, is_active=False)
    assert client_for(user).get("/api/dashboard/").status_code == 403


def test_role_catalog_is_ordered_from_the_top_with_assignable_flags(school, client_for):
    admin = make_user(school, "school_admin")
    catalog = client_for(admin).get("/api/roles/").json()
    assert [r["value"] for r in catalog[:3]] == ["director", "school_admin", "head_teacher"]
    assert catalog[-1]["value"] == "staff"
    flags = {r["value"]: r["assignable"] for r in catalog}
    assert flags["director"] is False and flags["school_admin"] is False and flags["head_teacher"] is True


def test_school_admin_cannot_raise_anyone_to_their_level_or_above(school, client_for):
    admin = make_user(school, "school_admin")
    teacher = make_user(school, "subject_teacher")
    membership = teacher.memberships.get()
    client = client_for(admin)
    for role in ("director", "school_admin"):
        response = client.post(
            "/api/role-assignments/", {"membership": membership.id, "role": role}, format="json"
        )
        assert response.status_code == 400, role
    ok = client.post(
        "/api/role-assignments/", {"membership": membership.id, "role": "head_teacher"}, format="json"
    )
    assert ok.status_code == 201


def test_nobody_changes_their_own_access(school, client_for):
    admin = make_user(school, "school_admin")
    membership = admin.memberships.get()
    response = client_for(admin).post(
        "/api/role-assignments/", {"membership": membership.id, "role": "bursar"}, format="json"
    )
    assert response.status_code == 400 and "your own access" in response.json()["detail"]


def test_lower_levels_cannot_edit_or_disable_higher_ones(school, director, client_for):
    admin = make_user(school, "school_admin")
    director_membership = director.memberships.get()
    client = client_for(admin)
    assert (
        client.patch(f"/api/users/{director_membership.id}/", {"is_active": False}, format="json").status_code
        == 400
    )
    role = RoleAssignment.objects.get(membership=director_membership)
    assert client.delete(f"/api/role-assignments/{role.id}/").status_code == 400
    director_membership.refresh_from_db()
    assert director_membership.is_active


def test_director_is_top_of_the_school(school, director, client_for):
    other = make_user(school, "school_admin")
    client = client_for(director)
    membership = other.memberships.get()
    assert (
        client.post(
            "/api/role-assignments/", {"membership": membership.id, "role": "director"}, format="json"
        ).status_code
        == 201
    )
    assert (
        client.patch(f"/api/users/{membership.id}/", {"title": "Co-owner"}, format="json").status_code == 200
    )


def test_roles_without_user_management_cannot_touch_accounts(school, head, client_for):
    assert client_for(head).get("/api/role-assignments/").status_code == 403
    assert client_for(head).get("/api/users/").status_code == 403


def test_temporary_permissions_only_from_what_you_hold(school, client_for):
    admin = make_user(school, "school_admin")
    teacher = make_user(school, "subject_teacher")
    membership = teacher.memberships.get()
    client = client_for(admin)
    expires = (timezone.now() + datetime.timedelta(days=2)).isoformat()
    denied = client.post(
        "/api/permission-grants/",
        {"membership": membership.id, "permission": "finance.view", "reason": "Audit", "expires_at": expires},
        format="json",
    )
    assert denied.status_code == 400
    granted = client.post(
        "/api/permission-grants/",
        {
            "membership": membership.id,
            "permission": "audit.view",
            "reason": "Help review edits",
            "expires_at": expires,
        },
        format="json",
    )
    assert granted.status_code == 201
    assert client_for(teacher).get("/api/audit-log/").status_code == 200


def test_platform_team_onboards_a_school_and_its_first_director(client_for):
    platform = UserFactory(is_platform_admin=True)
    client = client_for(platform)
    school = client.post(
        "/api/platform/schools/", {"name": "Hillside Primary", "kind": "day"}, format="json"
    ).json()
    admins = client.post(
        f"/api/platform/schools/{school['id']}/administrators/",
        {
            "username": "hillside.director",
            "first_name": "Ruth",
            "last_name": "Kintu",
            "password": "Strong-Pass-2026",
            "role": "director",
        },
        format="json",
    ).json()
    assert admins[0]["role"] == "director"
    from rest_framework.test import APIClient

    api = APIClient()
    me = api.post(
        "/api/auth/login/",
        {"school_code": school["code"], "username": "hillside.director", "password": "Strong-Pass-2026"},
        format="json",
    ).json()
    assert me["school"]["name"] == "Hillside Primary" and "users.manage" in me["perms"] and me["rank"] == 100
    assert School.objects.filter(pk=school["id"], is_active=True).exists()


def test_platform_team_cannot_read_school_records_or_manage_the_team(school, learners, client_for):
    platform = UserFactory(is_platform_admin=True)
    client = client_for(platform)
    assert client.get("/api/learners/", HTTP_X_SCHOOL_ID=str(school.id)).status_code == 403
    assert client.get("/api/platform/team/").status_code == 403


def test_super_admin_manages_the_platform_team(client_for):
    root = UserFactory(is_superuser=True, is_staff=True)
    client = client_for(root)
    created = client.post(
        "/api/platform/team/",
        {"username": "ops1", "first_name": "Ops", "last_name": "One", "password": "Strong-Pass-2026"},
        format="json",
    )
    assert created.status_code == 201 and created.json()["is_platform_admin"] is True
    assert {u["username"] for u in client.get("/api/platform/team/").json()["results"]} >= {
        "ops1",
        root.username,
    }
    me = client.patch(f"/api/platform/team/{root.id}/", {"is_active": False}, format="json")
    assert me.status_code == 400
