from django.conf import settings
from django.db import models

from apps.core.models import SchoolOwned
from apps.learners.models import Learner
from apps.schoolsetup.models import SchoolClass, Stream, Term


class AttendanceSession(SchoolOwned):
    """One roll call: a daily register for a class/stream, or one lesson (slot set)."""

    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    date = models.DateField(db_index=True)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.CASCADE)
    slot = models.ForeignKey("timetable.TimetableSlot", null=True, blank=True, on_delete=models.SET_NULL)
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["school_class", "stream", "date", "slot"],
                name="uniq_attendance_session",
                nulls_distinct=False,
            ),
        ]

    @property
    def is_lesson(self):
        return self.slot_id is not None


class AttendanceRecord(SchoolOwned):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        EXCUSED = "excused", "Excused"

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records")
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="attendance")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    reason = models.CharField(max_length=200, blank=True)
    version = models.PositiveIntegerField(
        default=1, help_text="Incremented on each change; used for offline sync"
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "learner"], name="uniq_attendance_record")]

    def save(self, *args, **kwargs):
        if self.pk:
            self.version += 1
        super().save(*args, **kwargs)
