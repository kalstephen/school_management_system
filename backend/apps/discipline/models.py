from django.db import models

from apps.core.models import SchoolOwned
from apps.learners.models import Learner


class DisciplineCase(SchoolOwned):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    class Severity(models.TextChoices):
        MINOR = "minor", "Minor"
        MAJOR = "major", "Major"
        CRITICAL = "critical", "Critical"

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="discipline_cases")
    date = models.DateField()
    category = models.CharField(max_length=100, help_text="e.g. Lateness, Fighting, Exam malpractice")
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MINOR)
    description = models.TextField()
    reported_by = models.CharField(max_length=200, blank=True)
    action_taken = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    closed_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]


class Sanction(SchoolOwned):
    case = models.ForeignKey(DisciplineCase, on_delete=models.CASCADE, related_name="sanctions")
    kind = models.CharField(max_length=100, help_text="e.g. Warning, Detention, Suspension, Parents called")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)


class CounsellingReferral(SchoolOwned):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="counselling_referrals")
    date = models.DateField()
    reason = models.TextField()
    referred_to = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]


class Achievement(SchoolOwned):
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="achievements")
    date = models.DateField()
    title = models.CharField(max_length=200)
    category = models.CharField(
        max_length=100, blank=True, help_text="e.g. Sports, Music, Academic, Leadership"
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
