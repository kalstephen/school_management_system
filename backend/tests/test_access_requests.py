"""The public website's "Request access" form and its follow-up in the owner console."""

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.subscriptions.models import AccessRequest

from .factories import UserFactory

pytestmark = pytest.mark.django_db

FORM = {
    "kind": "demo",
    "school_name": "Seeta Hill Primary",
    "contact_name": "Grace Namuli",
    "role": "Director",
    "phone": "0772 123 456",
    "email": "grace@example.com",
    "district": "Mukono",
    "levels": "Nursery, Primary",
    "learners": 420,
    "message": "We would like a demo before next term.",
}


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    from django.core.cache import cache

    cache.clear()


def test_anyone_can_send_a_request_and_the_team_is_emailed(client_for):
    UserFactory(is_platform_admin=True, email="team@spex.co.ug")
    response = APIClient().post("/api/public/access-requests/", FORM, format="json")
    assert response.status_code == 201 and response.json()["reference"].startswith("SPEX-")
    saved = AccessRequest.objects.get()
    assert saved.status == "new" and saved.school_name == "Seeta Hill Primary"
    assert len(mail.outbox) == 1 and "Seeta Hill Primary" in mail.outbox[0].subject


def test_request_needs_a_phone_and_bots_are_dropped():
    client = APIClient()
    assert (
        client.post("/api/public/access-requests/", {**FORM, "phone": "12"}, format="json").status_code == 400
    )
    bot = client.post("/api/public/access-requests/", {**FORM, "website": "spam.example"}, format="json")
    assert bot.status_code == 201 and not AccessRequest.objects.exists()


def test_requests_are_rate_limited(settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {"access_request": "2/hour"},
    }
    from rest_framework.settings import api_settings
    from rest_framework.throttling import ScopedRateThrottle

    api_settings.reload()
    ScopedRateThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES
    client = APIClient()
    codes = [client.post("/api/public/access-requests/", FORM, format="json").status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_owner_console_follows_up_and_schools_cannot_see_requests(school, head, client_for):
    AccessRequest.objects.create(**FORM)
    platform = client_for(UserFactory(is_platform_admin=True))
    rows = platform.get("/api/platform/requests/").json()["results"]
    assert rows[0]["kind_label"] == "Book a demo"
    updated = platform.patch(
        f"/api/platform/requests/{rows[0]['id']}/",
        {"status": "contacted", "notes": "Demo on Friday"},
        format="json",
    ).json()
    assert updated["status"] == "contacted" and updated["handled_by_name"]
    assert platform.get("/api/platform/overview/").json()["new_requests"] == 0
    assert client_for(head).get("/api/platform/requests/").status_code == 403
