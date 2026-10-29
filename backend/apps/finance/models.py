"""Finance records money going out (and optional non-fee income). Never fees."""

from django.conf import settings
from django.db import models

from apps.core.models import School, SchoolOwned
from apps.schoolsetup.models import Department, SchoolClass, Section, Term, term_for_date


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    MOBILE_MONEY = "mobile_money", "Mobile money"
    BANK = "bank", "Bank transfer"
    CHEQUE = "cheque", "Cheque"


class FinanceSettings(models.Model):
    """Approval limits (UGX): bursar alone up to bursar_limit, head teacher up to head_limit,
    director above that."""

    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name="finance_settings")
    bursar_limit = models.DecimalField(max_digits=14, decimal_places=0, default=200_000)
    head_limit = models.DecimalField(max_digits=14, decimal_places=0, default=2_000_000)

    def level_for(self, amount):
        if amount <= self.bursar_limit:
            return 1
        if amount <= self.head_limit:
            return 2
        return 3

    @classmethod
    def for_school(cls, school):
        return cls.objects.get_or_create(school=school)[0]


class ExpenseCategory(SchoolOwned):
    name = models.CharField(max_length=100)
    is_capital = models.BooleanField(
        default=False, help_text="Capital purchases are also added to the asset register"
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "expense categories"

    def __str__(self):
        return self.name


class ExpenseSubCategory(SchoolOwned):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name="sub_categories")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "expense sub-categories"

    def __str__(self):
        return self.name


class Supplier(SchoolOwned):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=200, blank=True)
    tin = models.CharField("TIN", max_length=30, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Requisition(SchoolOwned):
    """A staff member asks for money or items (e.g. lab chemicals). It climbs the ranks above
    the requester (head of department, DOS, head teacher, director for large amounts), reaches
    finance, who issue the money, and the requester then accounts for what was spent."""

    class Status(models.TextChoices):
        PENDING = "pending", "Going through approval"
        APPROVED = "approved", "Approved, waiting for finance"
        REJECTED = "rejected", "Not approved"
        DISBURSED = "disbursed", "Money issued, to be accounted for"
        ACCOUNTED = "accounted", "Accounted for"
        FULFILLED = "fulfilled", "Fulfilled"

    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    items = models.JSONField(
        default=list, blank=True, help_text='[{"item": "...", "qty": 2, "unit_cost": 5000}]'
    )
    estimated_amount = models.DecimalField(max_digits=14, decimal_places=0)
    needed_by = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decision_comment = models.CharField(max_length=300, blank=True)
    route = models.JSONField(default=list, blank=True, help_text="The approval steps, in order")
    step = models.PositiveSmallIntegerField(default=0, help_text="Index of the step it is waiting at")
    disbursed_amount = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    disbursement_method = models.CharField(max_length=15, choices=PaymentMethod.choices, blank=True)
    disbursed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    spent_amount = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    returned_amount = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    accountability_note = models.TextField(blank=True)
    receipt = models.FileField(upload_to="requisitions/", blank=True)
    accounted_submitted_at = models.DateTimeField(null=True, blank=True)
    accounted_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    accounted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Expense(SchoolOwned):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Awaiting approval"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"

    SPENT = (Status.APPROVED, Status.PAID)

    date = models.DateField(db_index=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.RESTRICT, related_name="expenses")
    sub_category = models.ForeignKey(ExpenseSubCategory, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    method = models.CharField(max_length=15, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    payee = models.CharField(max_length=200, blank=True)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="expenses"
    )
    reference = models.CharField(max_length=100, blank=True)
    receipt = models.FileField(upload_to="receipts/", blank=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.SET_NULL)
    school_class = models.ForeignKey(SchoolClass, null=True, blank=True, on_delete=models.SET_NULL)
    project = models.CharField(max_length=100, blank=True, help_text='e.g. "S4 mock exams", "Sports day"')
    term = models.ForeignKey(
        Term,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expenses",
        help_text="Finance period; set from the date",
    )
    period_override_reason = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    required_level = models.PositiveSmallIntegerField(default=1)
    requisition = models.ForeignKey(
        Requisition, null=True, blank=True, on_delete=models.SET_NULL, related_name="expenses"
    )
    recurring = models.ForeignKey("RecurringExpense", null=True, blank=True, on_delete=models.SET_NULL)
    paid_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date} {self.description} UGX {self.amount:,.0f}"

    def save(self, *args, **kwargs):
        if self.term_id is None or not self.period_override_reason:
            self.term = term_for_date(self.school, self.date) or self.term
        super().save(*args, **kwargs)


class Approval(SchoolOwned):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        AUTO = "auto", "Within the entering officer's limit"

    expense = models.ForeignKey(
        Expense, null=True, blank=True, on_delete=models.CASCADE, related_name="approvals"
    )
    requisition = models.ForeignKey(
        Requisition, null=True, blank=True, on_delete=models.CASCADE, related_name="approvals"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    level = models.PositiveSmallIntegerField()
    step = models.CharField(max_length=20, blank=True, help_text="Requisition step decided, e.g. dos")
    decision = models.CharField(max_length=10, choices=Decision.choices)
    comment = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["created_at"]


class RecurringExpense(SchoolOwned):
    class Frequency(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        TERMLY = "termly", "Each term"

    category = models.ForeignKey(ExpenseCategory, on_delete=models.RESTRICT)
    sub_category = models.ForeignKey(ExpenseSubCategory, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    method = models.CharField(max_length=15, choices=PaymentMethod.choices, default=PaymentMethod.BANK)
    payee = models.CharField(max_length=200, blank=True)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.MONTHLY)
    next_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.description} ({self.get_frequency_display()})"


class PettyCashFloat(SchoolOwned):
    name = models.CharField(max_length=100, default="Main float")
    custodian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    float_amount = models.DecimalField(max_digits=14, decimal_places=0, help_text="Target float (UGX)")
    replenish_below = models.DecimalField(
        max_digits=14, decimal_places=0, help_text="Ask for a top-up below this"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def balance(self):
        totals = self.entries.aggregate(
            topups=models.Sum("amount", filter=models.Q(kind="topup")),
            spent=models.Sum("amount", filter=models.Q(kind="spend")),
        )
        return (totals["topups"] or 0) - (totals["spent"] or 0)


class PettyCashEntry(SchoolOwned):
    class Kind(models.TextChoices):
        TOPUP = "topup", "Top-up"
        SPEND = "spend", "Spending"

    float = models.ForeignKey(PettyCashFloat, on_delete=models.CASCADE, related_name="entries")
    date = models.DateField()
    kind = models.CharField(max_length=6, choices=Kind.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    description = models.CharField(max_length=300)
    expense = models.OneToOneField(
        Expense, null=True, blank=True, on_delete=models.SET_NULL, related_name="petty_cash_entry"
    )

    class Meta:
        ordering = ["date", "id"]
        verbose_name_plural = "petty cash entries"


class PettyCashCount(SchoolOwned):
    """End-of-day cash count against the expected balance."""

    float = models.ForeignKey(PettyCashFloat, on_delete=models.CASCADE, related_name="counts")
    date = models.DateField()
    expected = models.DecimalField(max_digits=14, decimal_places=0)
    counted = models.DecimalField(max_digits=14, decimal_places=0)
    notes = models.CharField(max_length=300, blank=True)

    @property
    def difference(self):
        return self.counted - self.expected


class Budget(SchoolOwned):
    term = models.OneToOneField(Term, on_delete=models.CASCADE, related_name="budget")
    notes = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Budget {self.term}"


class BudgetLine(SchoolOwned):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    alerted_80 = models.BooleanField(default=False)
    alerted_100 = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["budget", "category"], name="uniq_budget_line")]


class PurchaseOrder(SchoolOwned):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent to supplier"
        PARTLY_RECEIVED = "partly_received", "Partly received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    supplier = models.ForeignKey(Supplier, on_delete=models.RESTRICT, related_name="purchase_orders")
    number = models.CharField(max_length=30)
    date = models.DateField()
    items = models.JSONField(
        default=list, help_text='[{"item": "Sugar 50kg", "qty": 4, "unit_price": 210000, "stock_item": id}]'
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-date"]

    @property
    def total(self):
        return sum((i.get("qty") or 0) * (i.get("unit_price") or 0) for i in self.items)


class Delivery(SchoolOwned):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="deliveries")
    date = models.DateField()
    items = models.JSONField(default=list, help_text='[{"stock_item": id, "item": "...", "qty": 2}]')
    received_by = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name_plural = "deliveries"


class SupplierBill(SchoolOwned):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PART_PAID = "part_paid", "Part paid"
        PAID = "paid", "Paid"

    supplier = models.ForeignKey(Supplier, on_delete=models.RESTRICT, related_name="bills")
    purchase_order = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.RESTRICT)
    reference = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=300)
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID)

    class Meta:
        ordering = ["-date"]

    @property
    def paid(self):
        return self.payments.aggregate(total=models.Sum("amount"))["total"] or 0

    @property
    def balance(self):
        return self.amount - self.paid


class SupplierPayment(SchoolOwned):
    """Paying a bill (in full or in part) records the expense at the time of payment."""

    bill = models.ForeignKey(SupplierBill, on_delete=models.CASCADE, related_name="payments")
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    method = models.CharField(max_length=15, choices=PaymentMethod.choices, default=PaymentMethod.BANK)
    reference = models.CharField(max_length=100, blank=True)
    expense = models.OneToOneField(
        Expense, null=True, blank=True, on_delete=models.SET_NULL, related_name="supplier_payment"
    )


class OtherIncome(SchoolOwned):
    """Non-fee money that funds expenses: capitation grants, donations, produce, hire."""

    class Source(models.TextChoices):
        CAPITATION = "capitation", "UPE/USE capitation grant"
        DONATION = "donation", "Donation"
        PRODUCE = "produce", "Sale of farm produce"
        HIRE = "hire", "Hall or facility hire"
        OTHER = "other", "Other"

    date = models.DateField()
    source = models.CharField(max_length=12, choices=Source.choices)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    received_from = models.CharField(max_length=200, blank=True)
    method = models.CharField(max_length=15, choices=PaymentMethod.choices, default=PaymentMethod.BANK)
    reference = models.CharField(max_length=100, blank=True)
    term = models.ForeignKey(Term, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-date"]
        verbose_name_plural = "other income"

    def save(self, *args, **kwargs):
        self.term = term_for_date(self.school, self.date) or self.term
        super().save(*args, **kwargs)
