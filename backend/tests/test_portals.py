"""Two separate doors: the school portal (School ID + username) never carries platform
rights, and the platform console is only for the platform team."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Membership, RoleAssignment
from apps.core.models import School

from .factories import UserFactory

pytestmark = pytest.mark.django_db


def sign_in(**body):
    api = APIClient()
    response = api.post("/api/auth/login/", body, format="json")
    return api, response


@pytest.fixture
def dual_account(school):
    """A school director who was also (wrongly) given platform-team rights."""
    user = UserFactory(username="dual", is_platform_admin=True)
    membership = Membership.objects.create(school=school, user=user)
    RoleAssignment.objects.create(school=school, membership=membership, role="director")
    return user


def test_school_sign_in_never_carries_platform_rights(school, dual_account):
    api, response = sign_in(school_code=school.code, username="dual", password="Pass-12345")
    me = response.json()
    assert response.status_code == 200
    assert (
        me["portal"] == "school" and me["user"]["is_platform_admin"] is False and me["is_superuser"] is False
    )
    assert me["school"]["code"] == school.code and "finance" in me["modules"]
    assert me["rank"] == 100  # director level, not above it
    assert api.get("/api/platform/overview/").status_code == 403
    assert api.get("/api/platform/schools/").status_code == 403
    assert api.get("/api/dashboard/").status_code == 200


def test_platform_console_gives_platform_rights_but_no_school(school, dual_account):
    api, response = sign_in(portal="platform", username="dual", password="Pass-12345")
    me = response.json()
    assert me["portal"] == "platform" and me["user"]["is_platform_admin"] is True and me["school"] is None
    assert api.get("/api/platform/overview/").status_code == 200
    assert api.get("/api/learners/").status_code == 403  # no school records from the console


def test_platform_console_refuses_school_accounts(school, head):
    _, response = sign_in(portal="platform", username="head", password="Pass-12345")
    assert response.status_code == 400 and "platform team" in response.json()["detail"]


def test_school_portal_needs_the_school_id(school, head):
    _, response = sign_in(username="head", password="Pass-12345")
    assert response.status_code == 400 and "school_code" in response.json()


def test_inactive_school_cannot_sign_in(school, head):
    School.objects.filter(pk=school.pk).update(is_active=False)
    _, response = sign_in(school_code=school.code, username="head", password="Pass-12345")
    assert response.status_code == 400 and "not active" in response.json()["detail"]


def test_super_admin_uses_the_console(client_for):
    root = UserFactory(username="root", is_superuser=True, is_staff=True)
    api, response = sign_in(portal="platform", username="root", password="Pass-12345")
    assert response.json()["is_superuser"] is True
    assert api.get("/api/platform/team/").status_code == 200
    _, response = sign_in(school_code="Anything-001", username="root", password="Pass-12345")
    assert response.status_code == 400  # not a member of any school: no school portal access
    assert root.is_superuser
