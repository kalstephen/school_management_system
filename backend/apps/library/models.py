from django.db import models
from django.utils import timezone

from apps.core.models import SchoolOwned
from apps.curriculum.models import Subject
from apps.learners.models import Learner
from apps.staff.models import StaffProfile


class Book(SchoolOwned):
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=200, blank=True)
    isbn = models.CharField("ISBN", max_length=20, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL)
    is_textbook = models.BooleanField(default=False, help_text="Issued to learners for the term")
    shelf = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class BookCopy(SchoolOwned):
    class Condition(models.TextChoices):
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        POOR = "poor", "Poor"
        LOST = "lost", "Lost"

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    barcode = models.CharField(max_length=50)
    condition = models.CharField(max_length=5, choices=Condition.choices, default=Condition.GOOD)

    class Meta:
        verbose_name_plural = "book copies"
        constraints = [models.UniqueConstraint(fields=["school", "barcode"], name="uniq_barcode")]

    def __str__(self):
        return f"{self.book} [{self.barcode}]"

    @property
    def is_on_loan(self):
        return self.loans.filter(returned_on__isnull=True).exists()


class Loan(SchoolOwned):
    copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE, related_name="loans")
    learner = models.ForeignKey(
        Learner, null=True, blank=True, on_delete=models.CASCADE, related_name="loans"
    )
    staff = models.ForeignKey(
        StaffProfile, null=True, blank=True, on_delete=models.CASCADE, related_name="loans"
    )
    issued_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField()
    returned_on = models.DateField(null=True, blank=True)
    condition_on_return = models.CharField(max_length=5, choices=BookCopy.Condition.choices, blank=True)

    class Meta:
        ordering = ["-issued_on"]

    @property
    def is_overdue(self):
        return self.returned_on is None and self.due_on < timezone.localdate()
