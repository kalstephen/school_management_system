from django.db import models

from apps.core.models import SchoolOwned
from apps.learners.models import Learner


class SickbayVisit(SchoolOwned):
    class Outcome(models.TextChoices):
        RETURNED_TO_CLASS = "class", "Returned to class"
        RESTED = "rested", "Rested in sickbay"
        SENT_HOME = "home", "Sent home"
        REFERRED = "referred", "Referred to hospital"

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="sickbay_visits")
    visited_at = models.DateTimeField()
    complaint = models.CharField(max_length=300)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    diagnosis = models.CharField(max_length=300, blank=True)
    treatment = models.TextField(blank=True)
    outcome = models.CharField(max_length=10, choices=Outcome.choices, default=Outcome.RETURNED_TO_CLASS)
    referred_to = models.CharField(max_length=200, blank=True)
    guardian_informed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-visited_at"]


class Immunisation(SchoolOwned):
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="immunisations")
    vaccine = models.CharField(max_length=100)
    dose = models.CharField(max_length=30, blank=True)
    date = models.DateField()
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-date"]
