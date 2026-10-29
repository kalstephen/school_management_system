"""Requisitions: up the ranks, finance issues the money, the requester accounts for it."""

import pytest

from apps.finance.models import Expense, ExpenseCategory, Requisition
from apps.schoolsetup.models import Department

from .factories import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def science(school):
    return Department.objects.get_or_create(school=school, name="Sciences")[0]


@pytest.fixture
def people(school, science, dos, head, director, bursar):
    teacher = make_user(school, "subject_teacher", username="teacher")
    hod = make_user(school, ("hod", "department", science.id), username="hod")
    return {"teacher": teacher, "hod": hod, "dos": dos, "head": head, "director": director, "bursar": bursar}


def _ask(client, science, amount, title="Lab chemicals"):
    return client.post(
        "/api/finance/requisitions/",
        {
            "title": title,
            "department": science.id,
            "estimated_amount": amount,
            "details": "For P7 practicals",
        },
        format="json",
    ).json()


def test_requisition_climbs_the_ranks_then_finance_and_accountability(school, science, people, client_for):
    teacher = client_for(people["teacher"])
    made = _ask(teacher, science, 300000)
    assert [s["step"] for s in made["steps"]] == ["hod", "dos", "head_teacher", "finance"]
    assert made["status"] == "pending" and made["waiting_for"] == "Head of department"
    url = f"/api/finance/requisitions/{made['id']}"

    # Nobody approves their own; the bursar cannot skip the queue.
    assert teacher.post(f"{url}/approve/").status_code == 400
    assert client_for(people["bursar"]).post(f"{url}/approve/").status_code == 400
    hod = client_for(people["hod"])
    assert [r["id"] for r in hod.get("/api/finance/requisitions/", {"waiting": 1}).json()["results"]] == [
        made["id"]
    ]
    hod.post(f"{url}/approve/", {"comment": "Needed for practicals"}, format="json")
    client_for(people["dos"]).post(f"{url}/approve/")
    after_head = client_for(people["head"]).post(f"{url}/approve/").json()
    assert after_head["status"] == "approved" and after_head["waiting_for"] == "Finance (issues the money)"
    assert [s["state"] for s in after_head["steps"]] == ["done", "done", "done", "current"]

    # Finance, at the end, issues the money; it is recorded as an expense.
    category = ExpenseCategory.objects.filter(school=school).first()
    bursar = client_for(people["bursar"])
    issued = bursar.post(
        f"{url}/disburse/",
        {"amount": 300000, "method": "mobile_money", "category": category.id},
        format="json",
    ).json()
    assert issued["status"] == "disbursed" and issued["waiting_for"] == "The requester to account"
    expense = Expense.objects.get(requisition_id=made["id"])
    assert expense.amount == 300000

    # The requester accounts for it; a mismatch needs an explanation.
    assert teacher.post(f"{url}/account/", {"spent_amount": 250000}, format="json").status_code == 400
    teacher.post(f"{url}/account/", {"spent_amount": 280000, "returned_amount": 20000}, format="json")
    done = bursar.post(f"{url}/confirm/").json()
    assert done["status"] == "accounted"
    expense.refresh_from_db()
    assert expense.amount == 280000


def test_route_depends_on_rank_and_amount(school, science, people, client_for):
    big = _ask(client_for(people["teacher"]), science, 3_000_000, "New laboratory benches")
    assert [s["step"] for s in big["steps"]] == ["hod", "dos", "head_teacher", "director", "finance"]
    from_dos = _ask(client_for(people["dos"]), science, 100000, "Exam paper")
    assert [s["step"] for s in from_dos["steps"]] == ["head_teacher", "finance"]


def test_rejection_needs_a_reason_and_tells_the_requester(school, science, people, client_for):
    from apps.communication.models import Notification

    made = _ask(client_for(people["teacher"]), science, 50000)
    url = f"/api/finance/requisitions/{made['id']}"
    hod = client_for(people["hod"])
    assert hod.post(f"{url}/reject/").status_code == 400
    rejected = hod.post(f"{url}/reject/", {"comment": "Use the stock in the store"}, format="json").json()
    assert rejected["status"] == "rejected" and rejected["steps"][0]["state"] == "rejected"
    assert Notification.objects.filter(
        user=people["teacher"], title__startswith="Requisition not approved"
    ).exists()
    assert Requisition.objects.get(pk=made["id"]).status == "rejected"
