"""School onboarding: full profile, School ID, module ticks, platform-created users with
inherited modules, sign-in with the School ID, and the platform overview."""

import pytest
from rest_framework.test import APIClient

from apps.core.models import School
from apps.core.modules import enabled_modules

from .factories import UserFactory

pytestmark = pytest.mark.django_db

PROFILE = {
    "name": "New Hope Junior School",
    "registration_number": "ME/P/10234",
    "emis_number": "EMIS-55102",
    "ownership": "private",
    "levels": "primary",
    "kind": "mixed",
    "region": "Central",
    "district": "Wakiso",
    "county": "Kyadondo",
    "sub_county": "Nansana",
    "parish": "Nabweru",
    "village": "Kazo",
    "phone": "0772 000 111",
    "head_teacher_name": "Sarah Nakato",
    "head_teacher_phone": "0700 111 222",
    "director_name": "Moses Kizito",
    "director_phone": "0701 333 444",
    "director_nin": "CM8800112233AB",
}


@pytest.fixture
def platform_client(client_for):
    return client_for(UserFactory(is_platform_admin=True))


def create_school(client, **extra):
    return client.post("/api/platform/schools/", {**PROFILE, **extra}, format="json")


def test_registering_a_school_with_profile_id_and_module_ticks(platform_client):
    response = create_school(platform_client, modules=["attendance", "assessment", "finance", "library"])
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["code"].startswith("NewHope-") and len(data["code"].split("-")[1]) == 3
    assert data["location"] == "Kazo, Nabweru, Nansana, Wakiso"
    assert data["director_name"] == "Moses Kizito" and data["head_teacher_name"] == "Sarah Nakato"
    ticked = {k for k, v in data["module_map"].items() if v}
    assert ticked == {"setup", "learners", "attendance", "assessment", "finance", "library"}


def test_school_id_can_be_chosen_and_must_be_unique(platform_client):
    first = create_school(platform_client, code="NewHope-003")
    assert first.status_code == 201 and first.json()["code"] == "NewHope-003"
    duplicate = create_school(platform_client, code="newhope-003")
    assert duplicate.status_code == 400 and "already used" in str(duplicate.json())
    bad = create_school(platform_client, code="New Hope!")
    assert bad.status_code == 400


def test_module_ticks_can_be_changed_later_and_required_ones_stay(platform_client):
    school_id = create_school(platform_client).json()["id"]
    response = platform_client.post(
        f"/api/platform/schools/{school_id}/modules/", {"modules": ["finance"]}, format="json"
    )
    assert {k for k, v in response.json()["module_map"].items() if v} == {"setup", "learners", "finance"}
    assert (
        platform_client.post(
            f"/api/platform/schools/{school_id}/module/",
            {"module": "learners", "enabled": False},
            format="json",
        ).status_code
        == 400
    )


def test_platform_creates_a_user_who_inherits_chosen_modules(platform_client):
    school = create_school(
        platform_client, code="NewHope-003", modules=["attendance", "assessment", "finance", "communication"]
    ).json()
    created = platform_client.post(
        "/api/platform/users/",
        {
            "school": school["id"],
            "username": "nh.bursar",
            "first_name": "Ruth",
            "last_name": "Akena",
            "password": "Strong-Pass-2026",
            "role": "bursar",
            "modules": ["finance", "communication"],
        },
        format="json",
    )
    assert created.status_code == 201, created.json()
    body = created.json()
    assert body["school_code"] == "NewHope-003" and body["school_location"].endswith("Wakiso")
    assert body["roles"] == ["Bursar / accounts"]

    api = APIClient()
    me = api.post(
        "/api/auth/login/",
        {"school_code": "NewHope-003", "username": "nh.bursar", "password": "Strong-Pass-2026"},
        format="json",
    ).json()
    assert me["school"]["code"] == "NewHope-003"
    assert set(me["modules"]) == {"setup", "learners", "finance", "communication"}
    assert api.get("/api/finance/expenses/").status_code == 200


def test_a_user_cannot_inherit_modules_the_school_lacks(platform_client):
    school = create_school(platform_client, modules=["attendance"]).json()
    response = platform_client.post(
        "/api/platform/users/",
        {
            "school": school["id"],
            "username": "x1",
            "first_name": "A",
            "last_name": "B",
            "password": "Strong-Pass-2026",
            "modules": ["finance"],
        },
        format="json",
    )
    assert response.status_code == 400 and "does not have" in str(response.json())


def test_user_level_modules_block_the_api(school, term, learners, client_for):
    from apps.accounts.models import Membership

    from .factories import make_user

    head = make_user(school, "head_teacher")
    Membership.objects.filter(user=head).update(modules=["attendance"])
    client = client_for(head)
    assert client.get("/api/learners/").status_code == 200  # required module
    assert client.get("/api/finance/expenses/").status_code == 403  # school has it, this person does not
    assert "finance" not in client.get("/api/auth/me/").json()["modules"]


def test_wrong_school_id_at_sign_in_is_refused(school, head):
    api = APIClient()
    response = api.post(
        "/api/auth/login/",
        {"school_code": "Nowhere-999", "username": "head", "password": "Pass-12345"},
        format="json",
    )
    assert response.status_code == 400 and "does not belong" in response.json()["detail"]
    ok = api.post(
        "/api/auth/login/",
        {"school_code": school.code.lower(), "username": "head", "password": "Pass-12345"},
        format="json",
    )
    assert ok.status_code == 200


def test_platform_overview_lists_schools_and_their_modules(platform_client, school):
    create_school(platform_client, modules=["finance"])
    data = platform_client.get("/api/platform/overview/").json()
    assert data["totals"]["schools"] == School.objects.count()
    row = next(r for r in data["schools"] if r["name"] == "New Hope Junior School")
    assert row["modules"]["finance"] is True and row["modules"]["library"] is False
    finance = next(m for m in data["module_adoption"] if m["key"] == "finance")
    assert finance["schools"] >= 1


def test_module_catalog_lists_every_module(client_for, head):
    catalog = client_for(head).get("/api/modules/").json()
    assert len(catalog) == 15
    assert {m["key"] for m in catalog if m["required"]} == {"setup", "learners"}


def test_existing_schools_keep_their_core_modules(school):
    assert "finance" in enabled_modules(school) and "library" not in enabled_modules(school)
