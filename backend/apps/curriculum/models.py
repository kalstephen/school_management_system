from django.db import models

from apps.core.models import SchoolOwned
from apps.schoolsetup.models import Department, SchoolClass, Section, Stream, Term


class Subject(SchoolOwned):
    """A subject at one level. The owner console loads the standard list; the school's
    director, DOS, head teacher or head of department can propose more, which count only once
    the head teacher, director or DOS approves them."""

    class Status(models.TextChoices):
        APPROVED = "approved", "Approved"
        PENDING = "pending", "Waiting for approval"
        REJECTED = "rejected", "Not approved"

    class Category(models.TextChoices):
        CORE = "core", "Compulsory"
        ELECTIVE = "elective", "Elective"
        PRINCIPAL = "principal", "A-Level principal"
        SUBSIDIARY = "subsidiary", "A-Level subsidiary"

    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20, blank=True)
    uneb_code = models.CharField("UNEB code", max_length=20, blank=True)
    level = models.CharField(max_length=10, choices=Section.Level.choices)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.CORE)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="subjects"
    )
    classes = models.ManyToManyField(
        SchoolClass, blank=True, related_name="subjects", help_text="Empty: every class at this level"
    )
    in_aggregate = models.BooleanField(default=False, help_text="Counts towards the PLE aggregate")
    order = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED, db_index=True)
    proposed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    proposal_note = models.CharField(max_length=300, blank=True, help_text="Why the school needs it")
    decided_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["level", "order", "name"]

    def __str__(self):
        return self.name


class Paper(SchoolOwned):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="papers")
    number = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["subject", "number"]
        constraints = [models.UniqueConstraint(fields=["subject", "number"], name="uniq_paper")]

    def __str__(self):
        return f"{self.subject.short_name or self.subject.name} P{self.number}"


class Combination(SchoolOwned):
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100, blank=True)
    principals = models.ManyToManyField(Subject, related_name="combinations")
    subsidiary = models.ForeignKey(
        Subject, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return self.code


class Competency(SchoolOwned):
    """A CBC learning outcome or activity of integration (AOI) for a subject and class."""

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="competencies")
    school_class = models.ForeignKey(SchoolClass, null=True, blank=True, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_aoi = models.BooleanField("Activity of integration", default=True)

    class Meta:
        verbose_name_plural = "competencies"

    def __str__(self):
        return f"{self.subject}: {self.topic}"


class SubjectAllocation(SchoolOwned):
    """Which teacher teaches which subject to which class (or one stream of it)."""

    teacher = models.ForeignKey("staff.StaffProfile", on_delete=models.CASCADE, related_name="allocations")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="allocations")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="allocations")
    stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.CASCADE)
    periods_per_week = models.PositiveSmallIntegerField(default=5)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["subject", "school_class", "stream"], name="uniq_allocation")
        ]

    def __str__(self):
        return f"{self.teacher} — {self.subject} {self.stream or self.school_class}"


class SchemeOfWork(SchoolOwned):
    class Kind(models.TextChoices):
        SCHEME = "scheme", "Scheme of work"
        LESSON_PLAN = "lesson_plan", "Lesson plan"

    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.SCHEME)
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, null=True, blank=True, on_delete=models.SET_NULL)
    file = models.FileField(upload_to="schemes/", blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.title
