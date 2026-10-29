from django.db import models

from apps.core.models import SchoolOwned
from apps.curriculum.models import Combination, Subject
from apps.schoolsetup.models import AcademicYear, House, SchoolClass, Stream, Term


class Residence(models.TextChoices):
    DAY = "day", "Day"
    BOARDING = "boarding", "Boarding"


class Learner(SchoolOwned):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        TRANSFERRED = "transferred", "Transferred out"
        LEFT = "left", "Left"
        COMPLETED = "completed", "Completed"

    adm_no = models.CharField("Admission number", max_length=30)
    lin = models.CharField("LIN", max_length=30, blank=True, help_text="Learner Identification Number")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)
    sex = models.CharField(max_length=1, choices=[("M", "Male"), ("F", "Female")])
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=50, default="Ugandan", blank=True)
    religion = models.CharField(max_length=50, blank=True)
    photo = models.ImageField(upload_to="learners/", blank=True)
    address = models.CharField(max_length=200, blank=True)
    district = models.CharField(max_length=100, blank=True)
    previous_school = models.CharField(max_length=200, blank=True)
    house = models.ForeignKey(House, null=True, blank=True, on_delete=models.SET_NULL)
    combination = models.ForeignKey(Combination, null=True, blank=True, on_delete=models.SET_NULL)
    residence = models.CharField(max_length=10, choices=Residence.choices, default=Residence.DAY)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    admitted_on = models.DateField(null=True, blank=True)
    year_of_entry = models.PositiveSmallIntegerField(null=True, blank=True)
    # Health fields are shown only to roles with health.view, and every view is logged.
    allergies = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True)
    has_medical_alert = models.BooleanField(default=False)
    special_needs = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        constraints = [models.UniqueConstraint(fields=["school", "adm_no"], name="uniq_adm_no")]
        indexes = [models.Index(fields=["school", "last_name", "first_name"])]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return " ".join(p for p in [self.first_name, self.other_names, self.last_name] if p)

    def current_enrolment(self):
        return (
            self.enrolments.select_related("term", "school_class", "stream")
            .order_by("-term__start_date")
            .first()
        )


class Guardian(SchoolOwned):
    """A contact for one or more learners (siblings share one guardian). No login."""

    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True, db_index=True)
    alt_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=200, blank=True)
    nin = models.CharField("National ID (NIN)", max_length=20, blank=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class LearnerGuardian(SchoolOwned):
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="guardian_links")
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name="learner_links")
    relationship = models.CharField(max_length=50, blank=True)
    is_primary = models.BooleanField(default=False)
    receives_email = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "guardian"], name="uniq_learner_guardian")]


class LearnerDocument(SchoolOwned):
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="learner_docs/")

    def __str__(self):
        return self.title


class Enrolment(SchoolOwned):
    """A learner's class and stream for one term."""

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="enrolments")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="enrolments")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.RESTRICT, related_name="enrolments")
    stream = models.ForeignKey(
        Stream, null=True, blank=True, on_delete=models.SET_NULL, related_name="enrolments"
    )
    residence = models.CharField(max_length=10, choices=Residence.choices, default=Residence.DAY)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "term"], name="uniq_enrolment")]

    def __str__(self):
        return f"{self.learner} — {self.stream or self.school_class} ({self.term})"


class SubjectEnrolment(SchoolOwned):
    """Which subjects a learner takes in a year (electives, A-Level combination)."""

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="subject_enrolments")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="learner_enrolments")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "subject", "academic_year"], name="uniq_subject_enrolment"
            )
        ]


class LearnerExit(SchoolOwned):
    """Transfer out, leaving, completion or expulsion. Sets the learner's status."""

    class Kind(models.TextChoices):
        TRANSFERRED = "transferred", "Transferred out"
        LEFT = "left", "Left"
        COMPLETED = "completed", "Completed"

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="exits")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    date = models.DateField()
    destination_school = models.CharField(max_length=200, blank=True)
    reason = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.learner.status = self.kind
        self.learner.save()


class StreamChange(SchoolOwned):
    """Mid-year class or stream change for one learner (e.g. a wrong placement)."""

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="stream_changes")
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    from_class = models.ForeignKey(SchoolClass, on_delete=models.RESTRICT, related_name="+")
    from_stream = models.ForeignKey(
        Stream, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    to_class = models.ForeignKey(SchoolClass, on_delete=models.RESTRICT, related_name="+")
    to_stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reason = models.CharField(max_length=300)
