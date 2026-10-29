from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import SchoolOwned


class AcademicYear(SchoolOwned):
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]
        constraints = [models.UniqueConstraint(fields=["school", "name"], name="uniq_year_name")]

    def __str__(self):
        return self.name


class Term(SchoolOwned):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="terms")
    number = models.PositiveSmallIntegerField(choices=[(1, "Term 1"), (2, "Term 2"), (3, "Term 3")])
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    next_term_begins = models.DateField(null=True, blank=True, help_text="Printed on report cards")
    timetable_published_at = models.DateTimeField(null=True, blank=True)
    timetable_published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-start_date"]
        constraints = [models.UniqueConstraint(fields=["academic_year", "number"], name="uniq_term_number")]

    def __str__(self):
        return f"Term {self.number} {self.academic_year.name}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "The term must end after it starts."})


class Section(SchoolOwned):
    class Level(models.TextChoices):
        NURSERY = "nursery", "Nursery"
        PRIMARY = "primary", "Primary"
        O_LEVEL = "olevel", "O-Level"
        A_LEVEL = "alevel", "A-Level"

    class RuleSet(models.TextChoices):
        NURSERY = "nursery", "Nursery (descriptive ratings)"
        GENERIC = "generic", "Marks and grades (e.g. P1–P3)"
        PLE = "ple", "Primary (PLE aggregates and divisions)"
        CBC = "cbc", "O-Level CBC (achievement levels)"
        UACE = "uace", "A-Level UACE (points)"

    name = models.CharField(max_length=50)
    level = models.CharField(max_length=10, choices=Level.choices)
    grading_rule_set = models.CharField(max_length=10, choices=RuleSet.choices)
    grading_scale = models.ForeignKey("GradingScale", null=True, blank=True, on_delete=models.SET_NULL)
    show_positions = models.BooleanField(default=True, help_text="Off by default for CBC classes")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class SchoolClass(SchoolOwned):
    section = models.ForeignKey(Section, on_delete=models.RESTRICT, related_name="classes")
    name = models.CharField(max_length=30)
    order = models.PositiveSmallIntegerField(default=0)
    is_candidate_class = models.BooleanField(
        default=False, help_text="P7, S4, S6: learners complete instead of promoting"
    )
    next_class = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    class_teacher = models.ForeignKey(
        "staff.StaffProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="classes_taught",
        help_text="Takes the register, writes report comments and sees the class's learners",
    )
    deputy_class_teacher = models.ForeignKey(
        "staff.StaffProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="classes_deputised",
        help_text="Stands in for the class teacher, with the same access to the class",
    )

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "class"
        verbose_name_plural = "classes"
        constraints = [models.UniqueConstraint(fields=["school", "name"], name="uniq_class_name")]

    def __str__(self):
        return self.name


class Stream(SchoolOwned):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="streams")
    name = models.CharField(max_length=30)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    class_teacher = models.ForeignKey(
        "staff.StaffProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="streams_taught"
    )
    deputy_class_teacher = models.ForeignKey(
        "staff.StaffProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="streams_deputised",
    )

    class Meta:
        ordering = ["school_class__order", "name"]
        constraints = [models.UniqueConstraint(fields=["school_class", "name"], name="uniq_stream")]

    def __str__(self):
        return (
            f"{self.school_class.name}{self.name}"
            if len(self.name) <= 2
            else f"{self.school_class.name} {self.name}"
        )


class House(SchoolOwned):
    name = models.CharField(max_length=50)
    colour = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.name


class Department(SchoolOwned):
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Club(SchoolOwned):
    name = models.CharField(max_length=100)
    patron = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name


class GradingScale(SchoolOwned):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    def band_for(self, score):
        """The highest band whose minimum the score reaches (so 79.5 falls in 70–79, not nowhere)."""
        if score is None:
            return None
        for band in sorted(self.bands.all(), key=lambda b: b.min_score, reverse=True):
            if score >= band.min_score:
                return band
        return None


class GradeBand(SchoolOwned):
    scale = models.ForeignKey(GradingScale, on_delete=models.CASCADE, related_name="bands")
    label = models.CharField(max_length=10)
    min_score = models.DecimalField(max_digits=6, decimal_places=2)
    max_score = models.DecimalField(max_digits=6, decimal_places=2)
    points = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    descriptor = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-min_score"]

    def __str__(self):
        return f"{self.label} ({self.min_score}–{self.max_score})"


class CalendarEvent(SchoolOwned):
    class Kind(models.TextChoices):
        HOLIDAY = "holiday", "Holiday"
        EVENT = "event", "School event"
        EXAM = "exam", "Exams"
        MEETING = "meeting", "Meeting"

    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.EVENT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        return self.title


def current_term(school, on=None):
    """The open term, else the latest term that has started."""
    on = on or timezone.localdate()
    term = Term.objects.filter(school=school, status=Term.Status.OPEN).order_by("-start_date").first()
    return term or term_for_date(school, on)


def term_for_date(school, on):
    """Finance periods: a term's period runs from its opening day to the day before the
    next term opens, so holiday spending lands in the term just ended."""
    return Term.objects.filter(school=school, start_date__lte=on).order_by("-start_date").first()
