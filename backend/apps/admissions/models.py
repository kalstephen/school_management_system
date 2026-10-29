from django.db import models
from django.utils import timezone

from apps.core.models import SchoolOwned
from apps.schoolsetup.models import SchoolClass, Stream, Term


class Application(SchoolOwned):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        INTERVIEW = "interview", "Interview scheduled"
        OFFERED = "offered", "Place offered"
        ADMITTED = "admitted", "Admitted"
        REJECTED = "rejected", "Not admitted"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Channel(models.TextChoices):
        PAPER = "paper", "Paper form"
        WALK_IN = "walk_in", "Walk-in"
        ONLINE = "online", "Online"

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)
    sex = models.CharField(max_length=1, choices=[("M", "Male"), ("F", "Female")])
    date_of_birth = models.DateField(null=True, blank=True)
    lin = models.CharField("LIN", max_length=30, blank=True)
    previous_school = models.CharField(max_length=200, blank=True)
    previous_results = models.CharField(
        max_length=200, blank=True, help_text="e.g. PLE aggregate 8, Division 1"
    )
    class_applied = models.ForeignKey(SchoolClass, on_delete=models.RESTRICT, related_name="+")
    term = models.ForeignKey(Term, null=True, blank=True, on_delete=models.SET_NULL)
    residence = models.CharField(
        max_length=10, choices=[("day", "Day"), ("boarding", "Boarding")], default="day"
    )
    guardian_name = models.CharField(max_length=200)
    guardian_phone = models.CharField(max_length=30)
    guardian_email = models.EmailField(blank=True)
    guardian_relationship = models.CharField(max_length=50, blank=True)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.PAPER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RECEIVED)
    interview_date = models.DateField(null=True, blank=True)
    interview_score = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    interview_notes = models.TextField(blank=True)
    placed_stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.SET_NULL)
    learner = models.OneToOneField("learners.Learner", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} → {self.class_applied}"


class Enquiry(SchoolOwned):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    subject = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    follow_up_on = models.DateField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"


class Visitor(SchoolOwned):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    purpose = models.CharField(max_length=200)
    person_to_see = models.CharField(max_length=200, blank=True)
    time_in = models.DateTimeField(default=timezone.now)
    time_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-time_in"]
