import datetime

import pytest

from apps.communication.models import Notification
from apps.finance.models import (
    Budget,
    BudgetLine,
    Expense,
    ExpenseCategory,
    PettyCashFloat,
    Supplier,
    SupplierBill,
)
from apps.schoolsetup.models import AcademicYear, Term
from apps.subscriptions.services import set_module

pytestmark = pytest.mark.django_db


@pytest.fixture
def feeding(school):
    return ExpenseCategory.objects.get(school=school, name="Feeding / kitchen")


def post_expense(client, category, amount, date=None, **extra):
    data = {
        "date": str(date or datetime.date.today()),
        "category": category.id,
        "description": "Sugar 50kg",
        "amount": amount,
        "method": "cash",
        **extra,
    }
    return client.post("/api/finance/expenses/", data, format="json")


def test_holiday_spending_lands_in_the_term_just_ended(school, term, today):
    year = term.academic_year
    term2 = Term.objects.create(
        school=school,
        academic_year=year,
        number=2,
        start_date=term.end_date + datetime.timedelta(days=21),
        end_date=term.end_date + datetime.timedelta(days=100),
    )
    holiday = term.end_date + datetime.timedelta(days=10)
    category = ExpenseCategory.objects.get(school=school, name="Utilities")
    expense = Expense.objects.create(
        school=school, date=holiday, category=category, description="Yaka", amount=50000
    )
    assert expense.term == term
    later = Expense.objects.create(
        school=school, date=term2.start_date, category=category, description="Yaka", amount=50000
    )
    assert later.term == term2


def test_approval_thresholds(school, term, feeding, bursar, head, director, client_for):
    bursar_client = client_for(bursar)
    small = post_expense(bursar_client, feeding, 150_000).json()
    assert (
        bursar_client.post(f"/api/finance/expenses/{small['id']}/submit/").json()["status"] == "approved"
    )  # within bursar limit
    medium = post_expense(bursar_client, feeding, 900_000).json()
    assert bursar_client.post(f"/api/finance/expenses/{medium['id']}/submit/").json()["status"] == "pending"
    refused = bursar_client.post(f"/api/finance/expenses/{medium['id']}/approve/")
    assert refused.status_code == 400 and "head teacher" in refused.json()["detail"]
    assert (
        client_for(head).post(f"/api/finance/expenses/{medium['id']}/approve/").json()["status"] == "approved"
    )
    big = post_expense(bursar_client, feeding, 5_000_000).json()
    bursar_client.post(f"/api/finance/expenses/{big['id']}/submit/")
    assert client_for(head).post(f"/api/finance/expenses/{big['id']}/approve/").status_code == 400
    assert (
        client_for(director).post(f"/api/finance/expenses/{big['id']}/approve/").json()["status"]
        == "approved"
    )
    paid = bursar_client.post(
        f"/api/finance/expenses/{big['id']}/pay/", {"reference": "CHQ 0042"}, format="json"
    ).json()
    assert paid["status"] == "paid" and paid["reference"] == "CHQ 0042"
    edit = bursar_client.patch(f"/api/finance/expenses/{big['id']}/", {"amount": 1}, format="json")
    assert edit.status_code == 400


def test_validation_and_rejection(school, term, feeding, bursar, head, client_for):
    client = client_for(bursar)
    assert post_expense(client, feeding, 0).status_code == 400
    expense = post_expense(client, feeding, 900_000).json()
    client.post(f"/api/finance/expenses/{expense['id']}/submit/")
    head_client = client_for(head)
    assert (
        head_client.post(f"/api/finance/expenses/{expense['id']}/reject/", {}, format="json").status_code
        == 400
    )
    rejected = head_client.post(
        f"/api/finance/expenses/{expense['id']}/reject/", {"comment": "Get 3 quotes"}, format="json"
    ).json()
    assert rejected["status"] == "rejected" and rejected["approvals"][-1]["comment"] == "Get 3 quotes"


def test_petty_cash(school, term, feeding, bursar, client_for):
    petty = PettyCashFloat.objects.create(
        school=school, custodian=bursar, float_amount=300_000, replenish_below=100_000
    )
    client = client_for(bursar)
    client.post(f"/api/finance/petty-cash/{petty.id}/topup/", {"amount": 300_000}, format="json")
    client.post(
        f"/api/finance/petty-cash/{petty.id}/spend/",
        {"amount": 250_000, "description": "Charcoal", "category": feeding.id},
        format="json",
    )
    too_much = client.post(
        f"/api/finance/petty-cash/{petty.id}/spend/",
        {"amount": 60_000, "description": "x", "category": feeding.id},
        format="json",
    )
    assert too_much.status_code == 400
    state = client.get(f"/api/finance/petty-cash/{petty.id}/").json()
    assert state["balance"] == 50_000 and state["needs_replenishment"] is True
    assert Expense.objects.get(project__startswith="Petty cash").status == "paid"
    book = client.get(f"/api/finance/petty-cash/{petty.id}/book/").json()
    assert book["closing"] == 50_000 and len(book["rows"]) == 2
    count = client.post(
        f"/api/finance/petty-cash/{petty.id}/count/", {"counted": 48_000}, format="json"
    ).json()
    assert count["difference"] == "-2000"


def test_budget_alerts_and_budget_vs_actual(school, term, feeding, bursar, client_for):
    budget = Budget.objects.create(school=school, term=term)
    BudgetLine.objects.create(school=school, budget=budget, category=feeding, amount=1_000_000)
    client = client_for(bursar)
    for amount in (150_000,) * 6:  # 900,000 = 90%
        expense = post_expense(client, feeding, amount).json()
        client.post(f"/api/finance/expenses/{expense['id']}/submit/")
    assert Notification.objects.filter(title="Budget alert", body__contains="90%").exists()
    report = client.get(f"/api/finance/reports/budget-vs-actual/?term={term.id}").json()
    line = next(l for l in report["lines"] if l["category"] == "Feeding / kitchen")
    assert line["actual"] == 900_000 and line["status"] == "warning"
    xlsx = client.get(f"/api/finance/reports/budget-vs-actual/?term={term.id}&download=xlsx")
    assert xlsx["Content-Type"].startswith("application/vnd.openxmlformats")


def test_supplier_bill_part_payment(school, term, feeding, bursar, head, client_for):
    supplier = Supplier.objects.create(school=school, name="Mukwano Traders")
    bill = SupplierBill.objects.create(
        school=school,
        supplier=supplier,
        category=feeding,
        description="Beans 10 bags",
        date=datetime.date.today(),
        amount=1_500_000,
    )
    client = client_for(head)
    client.post(f"/api/finance/bills/{bill.id}/pay/", {"amount": 500_000, "method": "bank"}, format="json")
    bill.refresh_from_db()
    assert bill.status == "part_paid" and bill.balance == 1_000_000
    assert (
        client.post(f"/api/finance/bills/{bill.id}/pay/", {"amount": 2_000_000}, format="json").status_code
        == 400
    )
    statement = client.get(f"/api/finance/suppliers/{supplier.id}/statement/").json()
    assert statement["amount_owed"] == 1_000_000
    assert Expense.objects.filter(supplier=supplier, status="paid").count() == 1


def test_termly_statement_cost_per_learner_and_other_income(
    school, term, learners, feeding, bursar, client_for
):
    client = client_for(bursar)
    expense = post_expense(client, feeding, 200_000).json()
    client.post(f"/api/finance/expenses/{expense['id']}/submit/")
    client.post(
        "/api/finance/other-income/",
        {
            "date": str(datetime.date.today()),
            "source": "capitation",
            "description": "UPE grant",
            "amount": 1_000_000,
        },
        format="json",
    )
    statement = client.get(f"/api/finance/reports/termly/?term={term.id}").json()
    assert (
        statement["total"] == 200_000
        and statement["learners"] == 4
        and statement["cost_per_learner"] == 50_000
    )
    assert statement["net_cash_position"] == 800_000
    school.other_income_enabled = False
    school.save()
    assert client.get("/api/finance/other-income/").status_code == 400


def test_capital_purchase_goes_to_asset_register_when_stores_on(school, term, bursar, head, client_for):
    from apps.stores.models import Asset

    set_module(school, "stores", True)
    capital = ExpenseCategory.objects.get(school=school, name="Capital purchases")
    client = client_for(bursar)
    assert (
        post_expense(client_for(head), capital, 10).status_code == 403
    )  # the head approves, the bursar enters
    expense = post_expense(client, capital, 1_800_000, description="Desktop computer").json()
    client.post(f"/api/finance/expenses/{expense['id']}/submit/")
    assert not Asset.objects.filter(expense_id=expense["id"]).exists()  # still awaiting the head teacher
    client_for(head).post(f"/api/finance/expenses/{expense['id']}/approve/")
    assert Asset.objects.filter(expense_id=expense["id"], purchase_cost=1_800_000).exists()


def test_recurring_expenses(school, term, feeding):
    from apps.finance.models import RecurringExpense
    from apps.finance.services import generate_recurring

    start = datetime.date.today() - datetime.timedelta(days=65)
    RecurringExpense.objects.create(
        school=school, category=feeding, description="Rent", amount=400_000, next_date=start
    )
    assert generate_recurring(school) == 3  # this month and the two before
    assert generate_recurring(school) == 0


def test_last_year_comparison(school, term, feeding, today):
    old_year = AcademicYear.objects.create(
        school=school,
        name=str(today.year - 1),
        start_date=today - datetime.timedelta(days=430),
        end_date=today - datetime.timedelta(days=100),
    )
    old_term = Term.objects.create(
        school=school,
        academic_year=old_year,
        number=1,
        start_date=today - datetime.timedelta(days=420),
        end_date=today - datetime.timedelta(days=330),
    )
    Expense.objects.create(
        school=school, date=old_term.start_date, category=feeding, description="x", amount=100, status="paid"
    )
    Expense.objects.create(
        school=school, date=today, category=feeding, description="x", amount=150, status="paid"
    )
    from apps.finance.reports import same_term_last_year

    rows = same_term_last_year(school, term)["rows"]
    assert rows[0]["change_percent"] == 50.0


def test_finance_users_manage_categories_and_sub_categories(school, term, bursar, client_for):
    from apps.finance.models import Expense

    client = client_for(bursar)
    made = client.post(
        "/api/finance/categories/",
        {"name": "Science fair", "sub_category_names": ["Exam printing", "Textbooks", " "]},
        format="json",
    ).json()
    assert sorted(s["name"] for s in made["sub_categories"]) == ["Exam printing", "Textbooks"]
    assert client.post("/api/finance/categories/", {"name": "science FAIR"}, format="json").status_code == 400

    printing = next(s for s in made["sub_categories"] if s["name"] == "Exam printing")
    expense = client.post(
        "/api/finance/expenses/",
        {
            "date": str(term.start_date),
            "amount": 50000,
            "category": made["id"],
            "sub_category": printing["id"],
            "description": "BOT papers",
        },
        format="json",
    )
    assert expense.status_code == 201, expense.json()
    # A sub-category of another category is refused.
    other = client.post(
        "/api/finance/categories/",
        {"name": "School trips", "sub_category_names": ["Bus hire"]},
        format="json",
    ).json()
    wrong = client.post(
        "/api/finance/expenses/",
        {
            "date": str(term.start_date),
            "amount": 1000,
            "category": made["id"],
            "sub_category": other["sub_categories"][0]["id"],
            "description": "x",
        },
        format="json",
    )
    assert wrong.status_code == 400

    # Adding works; removing one an expense uses is refused and nothing changes.
    url = f"/api/finance/categories/{made['id']}/"
    assert (
        client.patch(
            url, {"sub_category_names": ["Exam printing", "Textbooks", "Chalk"]}, format="json"
        ).status_code
        == 200
    )
    refused = client.patch(url, {"name": "Academic", "sub_category_names": ["Textbooks"]}, format="json")
    assert refused.status_code == 400 and "Exam printing" in str(refused.json())
    assert client.get(url).json()["name"] == "Science fair"
    removed = client.patch(url, {"sub_category_names": ["Exam printing", "Chalk"]}, format="json").json()
    assert sorted(s["name"] for s in removed["sub_categories"]) == ["Chalk", "Exam printing"]
    assert client.delete(url).status_code == 400 and Expense.objects.filter(category_id=made["id"]).exists()
    assert client.delete(f"/api/finance/categories/{other['id']}/").status_code == 204
