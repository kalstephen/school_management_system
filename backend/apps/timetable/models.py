from django.db import models

from apps.core.models import SchoolOwned
from apps.curriculum.models import Subject
from apps.schoolsetup.models import SchoolClass, Stream, Term
from apps.staff.models import StaffProfile

DAYS = [(1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"), (5, "Friday"), (6, "Saturday")]


class Period(SchoolOwned):
    name = models.CharField(max_length=30)
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveSmallIntegerField()
    is_break = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"


class Room(SchoolOwned):
    name = models.CharField(max_length=50)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=50, blank=True, help_text="e.g. Classroom, Laboratory, Computer lab")

    def __str__(self):
        return self.name


class TimetableSlot(SchoolOwned):
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name="slots")
    day = models.PositiveSmallIntegerField(choices=DAYS)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(
        StaffProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="slots"
    )
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["day", "period__order"]

    def __str__(self):
        return (
            f"{self.get_day_display()} {self.period.name}: {self.subject} {self.stream or self.school_class}"
        )


class Substitution(SchoolOwned):
    slot = models.ForeignKey(TimetableSlot, on_delete=models.CASCADE, related_name="substitutions")
    date = models.DateField()
    substitute = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="substitutions")
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["slot", "date"], name="uniq_substitution")]
