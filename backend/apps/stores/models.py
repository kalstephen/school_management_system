from django.db import models
from django.db.models import Q, Sum

from apps.core.models import SchoolOwned
from apps.learners.models import Learner
from apps.schoolsetup.models import SchoolClass, Section, Term


class Store(SchoolOwned):
    name = models.CharField(max_length=100, help_text="e.g. Food store, Stationery, Cleaning")
    keeper = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name


class Item(SchoolOwned):
    store = models.ForeignKey(Store, on_delete=models.RESTRICT, related_name="items")
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=30, default="pcs", help_text="e.g. kg, bags, reams, pcs")
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["store", "name"]

    def __str__(self):
        return f"{self.name} ({self.unit})"

    @property
    def quantity(self):
        totals = self.movements.aggregate(
            inn=Sum("quantity", filter=Q(kind="in")),
            out=Sum("quantity", filter=Q(kind="out")),
            adj=Sum("quantity", filter=Q(kind="adjust")),
        )
        return (totals["inn"] or 0) - (totals["out"] or 0) + (totals["adj"] or 0)


class StockMovement(SchoolOwned):
    class Kind(models.TextChoices):
        IN = "in", "Stock in"
        OUT = "out", "Stock out"
        ADJUST = "adjust", "Adjustment (count)"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="movements")
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    kind = models.CharField(max_length=6, choices=Kind.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    reference = models.CharField(max_length=100, blank=True)
    issued_to = models.CharField(max_length=200, blank=True, help_text="Kitchen, department or person")
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-date", "-id"]


class Requirement(SchoolOwned):
    """Scholastic requirement each learner brings, e.g. 2 reams, 1 broom, 4 toilet rolls."""

    name = models.CharField(max_length=100)
    item = models.ForeignKey(
        Item, null=True, blank=True, on_delete=models.SET_NULL, help_text="Stock item it adds to"
    )
    quantity_per_learner = models.DecimalField(max_digits=8, decimal_places=2)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} × {self.quantity_per_learner}"


class RequirementClearance(SchoolOwned):
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name="clearances")
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="requirement_clearances")
    quantity_brought = models.DecimalField(max_digits=8, decimal_places=2)
    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["requirement", "learner"], name="uniq_requirement_clearance")
        ]


class Asset(SchoolOwned):
    class Condition(models.TextChoices):
        NEW = "new", "New"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        POOR = "poor", "Poor"
        DISPOSED = "disposed", "Disposed"

    name = models.CharField(max_length=200)
    tag = models.CharField(max_length=50, blank=True, help_text="Asset tag or serial number")
    category = models.CharField(
        max_length=100, blank=True, help_text="e.g. Furniture, ICT, Vehicle, Lab equipment"
    )
    location = models.CharField(max_length=100, blank=True)
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.GOOD)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    custodian = models.CharField(max_length=200, blank=True)
    expense = models.ForeignKey(
        "finance.Expense", null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
